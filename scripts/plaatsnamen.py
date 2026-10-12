#!/usr/bin/env python3
"""Beoordeelt namen tegen een lijst met plaatsen, om verkeerd gespelde plaatsnamen te vinden.

De spellingtoets kent geen namen (OpenTaal bevat er geen), dus een goed gespelde plaats
en een verkeerd gespelde krijgen dezelfde melding. Dit helpt daarbij, zonder te doen alsof
het een spellingtoets voor namen is. Elke naam krijgt een van drie uitkomsten:

  bekend    de naam komt voor in GeoNames: geen aandacht nodig
  twijfel   de naam komt niet voor, maar lijkt op een bekende plaats; de suggestie staat
            erbij. Dit is een hint, geen oordeel: het kan ook een organisatie of een
            persoon zijn die toevallig op een plaats lijkt
  onbekend  de naam komt niet voor en lijkt op niets: organisatie, persoon of woord uit
            een andere taal. Hier zegt de lijst niets over

Bron: GeoNames (https://www.geonames.org), licentie CC BY 4.0. De workflow haalt per run
`cities1000.zip`, `admin1CodesASCII.txt` en `countryInfo.txt` op in data/geonames/. Alleen
de standaardbibliotheek van Python.

Meerwoordsnamen ("La Paz", "Haut-Mbomou") worden per woord getoetst: de tokenizer van de
crawler levert ze toch al los aan. Accenten tellen niet mee: "Cordoba" en "Córdoba" zijn
beide bekend.
"""

import re
import unicodedata
import zipfile
from pathlib import Path

# Een bekende plaats mag als suggestie dienen vanaf dit aantal inwoners. De volledige lijst
# (vanaf 1000 inwoners) telt voor "bekend", maar als suggestiebron levert ze te veel
# toevallige gelijkenissen op met gewone woorden.
MIN_INWONERS_SUGGESTIE = 15000

TOKENSPLITS = re.compile(r"[\s\-'’.,/()]+")


def normaliseer(tekst):
    """Kleine letters, zonder accenten, rechte apostrof."""
    ontleed = unicodedata.normalize("NFKD", tekst.replace("’", "'"))
    return "".join(t for t in ontleed if not unicodedata.combining(t)).casefold()


def tokens(naam):
    """De losse woorden van een naam, genormaliseerd, zonder leesteken en cijfers."""
    return [t for t in TOKENSPLITS.split(normaliseer(naam))
            if len(t) >= 2 and t.isalpha()]


def _is_latijns(token):
    # De pagina's zijn Nederlands; woorden in andere schriften komen niet voor en
    # kosten alleen geheugen.
    return all(ord(teken) < 0x250 for teken in token)


def afstand(a, b, grens):
    """Damerau-Levenshtein (omwisseling van twee letters telt als één fout), of grens+1.

    Stopt zodra het niet meer onder de grens kan komen; de meeste kandidaten vallen zo
    na een paar letters af.
    """
    if abs(len(a) - len(b)) > grens:
        return grens + 1
    vorige2 = None
    vorige = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        huidige = [i]
        for j, cb in enumerate(b, 1):
            kosten = 0 if ca == cb else 1
            waarde = min(vorige[j] + 1, huidige[j - 1] + 1, vorige[j - 1] + kosten)
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                waarde = min(waarde, vorige2[j - 2] + 1)
            huidige.append(waarde)
        if min(huidige) > grens:
            return grens + 1
        vorige2, vorige = vorige, huidige
    return vorige[-1]


def toegestane_afstand(lengte):
    """Hoeveel fouten we toelaten. Korte woorden niet: daar is elke gelijkenis toeval."""
    if lengte < 5:
        return 0
    return 1 if lengte < 9 else 2


class Plaatsnamen:
    def __init__(self):
        self.bekend = set()            # alle genormaliseerde woorden uit plaatsnamen
        self.kandidaten = {}           # (eerste letter, lengte) -> {token: (inwoners, weergave)}
        self._cache = {}

    # --- opbouwen --------------------------------------------------------

    def voeg_bekend_toe(self, naam):
        for token in tokens(naam):
            if _is_latijns(token):
                self.bekend.add(token)

    def voeg_kandidaat_toe(self, naam, inwoners):
        """Een naam die als suggestie mag dienen, met zijn weergave (met accenten)."""
        for ruw in TOKENSPLITS.split(naam.replace("’", "'")):
            token = normaliseer(ruw)
            if len(token) < 5 or not token.isalpha() or not _is_latijns(token):
                continue
            sleutel = (token[0], len(token))
            emmer = self.kandidaten.setdefault(sleutel, {})
            if token not in emmer or inwoners > emmer[token][0]:
                emmer[token] = (inwoners, ruw)

    @classmethod
    def uit_namen(cls, namen, kandidaten=None):
        """Voor tests: een kleine lijst. `kandidaten` is standaard gelijk aan `namen`."""
        zelf = cls()
        for naam in namen:
            zelf.voeg_bekend_toe(naam)
        for naam in (namen if kandidaten is None else kandidaten):
            zelf.voeg_kandidaat_toe(naam, MIN_INWONERS_SUGGESTIE)
        return zelf

    @classmethod
    def laad(cls, map_pad):
        """Leest de GeoNames-bestanden uit `map_pad`. None als ze er niet zijn."""
        map_pad = Path(map_pad)
        steden = map_pad / "cities1000.zip"
        if not steden.exists():
            return None
        zelf = cls()

        with zipfile.ZipFile(steden) as archief:
            naam = next(n for n in archief.namelist() if n.endswith(".txt"))
            with archief.open(naam) as bestand:
                for regel in bestand:
                    kolommen = regel.decode("utf-8").rstrip("\n").split("\t")
                    if len(kolommen) < 15:
                        continue
                    hoofdnaam, ascii_naam, alternatief = kolommen[1], kolommen[2], kolommen[3]
                    try:
                        inwoners = int(kolommen[14])
                    except ValueError:
                        inwoners = 0
                    for naam_ in (hoofdnaam, ascii_naam):
                        zelf.voeg_bekend_toe(naam_)
                    # Alternatieve namen: alleen om te weten dat een schrijfwijze bestaat.
                    for alt in alternatief.split(","):
                        if alt and len(alt) <= 40:
                            zelf.voeg_bekend_toe(alt)
                    if inwoners >= MIN_INWONERS_SUGGESTIE:
                        zelf.voeg_kandidaat_toe(hoofdnaam, inwoners)
                        zelf.voeg_kandidaat_toe(ascii_naam, inwoners)

        # Regio's en landen: "Antioquia", "Noord-Kivu" en dergelijke. Landen en regio's
        # staan niet in de stedenlijst. Ze tellen zwaar mee als suggestie.
        regios = map_pad / "admin1CodesASCII.txt"
        if regios.exists():
            for regel in regios.read_text(encoding="utf-8").splitlines():
                kolommen = regel.split("\t")
                for naam_ in kolommen[1:3]:
                    zelf.voeg_bekend_toe(naam_)
                    zelf.voeg_kandidaat_toe(naam_, MIN_INWONERS_SUGGESTIE * 100)
        landen = map_pad / "countryInfo.txt"
        if landen.exists():
            for regel in landen.read_text(encoding="utf-8").splitlines():
                if regel.startswith("#"):
                    continue
                kolommen = regel.split("\t")
                for naam_ in kolommen[4:6]:
                    zelf.voeg_bekend_toe(naam_)
                    zelf.voeg_kandidaat_toe(naam_, MIN_INWONERS_SUGGESTIE * 1000)
        return zelf

    # --- beoordelen ------------------------------------------------------

    def beoordeel(self, naam):
        """Geeft {"plaats_status": ..., "suggestie": ...}."""
        if naam not in self._cache:
            self._cache[naam] = self._beoordeel(naam)
        return self._cache[naam]

    def _beoordeel(self, naam):
        delen = tokens(naam)
        if not delen:
            return {"plaats_status": "onbekend", "suggestie": None}
        onbekend = [t for t in delen if t not in self.bekend]
        if not onbekend:
            return {"plaats_status": "bekend", "suggestie": None}
        for token in onbekend:
            suggestie = self._dichtstbij(token)
            if suggestie:
                return {"plaats_status": "twijfel", "suggestie": suggestie}
        return {"plaats_status": "onbekend", "suggestie": None}

    def _dichtstbij(self, token):
        grens = toegestane_afstand(len(token))
        if not grens or not token.isalpha() or not _is_latijns(token):
            return None
        beste = None  # (afstand, -inwoners, weergave)
        for lengte in range(len(token) - grens, len(token) + grens + 1):
            for kandidaat, (inwoners, weergave) in self.kandidaten.get((token[0], lengte), {}).items():
                d = afstand(token, kandidaat, grens)
                if d <= grens:
                    sleutel = (d, -inwoners, weergave)
                    if beste is None or sleutel < beste:
                        beste = sleutel
        return beste[2] if beste else None


def samenvatting(bevindingen, max_twijfel=40):
    """Een korte tekst voor het logboek: hoeveel van elk, en de eerste twijfelgevallen."""
    per_naam = {b["woord"]: b for b in bevindingen if b.get("plaats_status")}
    telling = {}
    twijfel = {}
    for naam, b in per_naam.items():
        telling[b["plaats_status"]] = telling.get(b["plaats_status"], 0) + 1
        if b["plaats_status"] == "twijfel":
            twijfel[naam] = b["suggestie"]
    regels = ["Plaatsnamen (unieke namen): " + ", ".join(f"{n} {s}" for s, n in sorted(telling.items()))]
    for woord, suggestie in sorted(twijfel.items())[:max_twijfel]:
        regels.append(f"  twijfel: {woord} -> {suggestie}")
    return "\n".join(regels)
