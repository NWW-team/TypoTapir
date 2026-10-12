#!/usr/bin/env python3
"""SpellingSpeurneus - zoekt spelfouten op een website, op verzoek.

Draait op de standaardbibliotheek van Python. Geen pip install nodig.

    python3 scripts/crawl.py --bron demo --max-paginas 5
    python3 scripts/crawl.py --bron reisadvies --max-paginas 10
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from plaatsnamen import Plaatsnamen, samenvatting
from voortgang import meld, run_url

SITE = "https://www.nederlandwereldwijd.nl"
PROJECT_URL = "https://github.com/NWW-team/SpellingSpeurneus"
USER_AGENT = f"SpellingSpeurneus/0.1 (+{PROJECT_URL})"

# De delen van de site die je kunt kiezen. Een deel is een pad: alles daarachter hoort
# erbij ("/reisadvies" en "/reisadvies/albanie", niet "/reisadvies-iets"). De pagina's
# staan verspreid over de sitemaps van de site (de visumpagina's zitten in de grote
# "paginas"-sitemap), dus we lezen ze allemaal en houden over wat onder het pad valt.
DELEN = {
    "reisadvies": "/reisadvies",
    "visum-nederland": "/visum-nederland",
    "caribisch-visum": "/caribisch-visum",
    "ambassades": "/contact/ambassades-consulaten-generaal",
}
SITEMAP_INDEX = f"{SITE}/sitemap.xml"

WORTEL = Path(__file__).resolve().parent.parent
LEESTEKENS = " \t\n\r.,;:!?()[]{}<>\"'“”‘’„…*•·|/\\&%=–—@#$^~`-"
# Tekens zonder breedte. Ze staan soms onzichtbaar in de content en maken
# van een gewoon woord een onbekend woord.
ONZICHTBAAR = str.maketrans("", "", "\u200b\u200c\u200d\u2060\ufeff\u00ad")
# Haakjes en schuine strepen plakken woorden aan elkaar: "(bus)chauffeur",
# "familie/vrienden". Daar splitsen we op, zodat elk deel apart wordt getoetst.
SPLITSERS = re.compile(r"[\s/()\[\]]+")
# Een punt middenin een woord wijst op een vergeten spatie, behalve bij een
# webadres. Deze staarten laten we daarom met rust.
DOMEINEN = (".com", ".nl", ".org", ".net", ".eu", ".gov", ".int")
# Resten van het sjabloon of het CMS die zichtbaar in de tekst staan. Op
# reisadvies/estland stond zo het woord "undefined" boven aan de pagina.
#
# Deze zoeken we apart op, want de gewone spellingtoets ziet ze niet allemaal:
# "[object Object]" en "{{titel}}" worden op de haakjes stukgeknipt en leveren
# dan "object" en "titel" op, en dat zijn gewone Nederlandse woorden. Zo'n rest
# glipt er dus geruisloos doorheen, terwijl een bezoeker hem wel ziet staan.
#
# Hoofdlettergevoelig: JavaScript schrijft undefined, null, NaN en Infinity
# precies zo, en dat scheelt treffers op Nederlandse woorden die erop lijken.
SJABLOONRESTEN = re.compile(
    r"\[object [A-Za-z]+\]"
    r"|\{\{[^{}]{0,60}\}\}"
    r"|\$\{[^{}]{0,60}\}"
    r"|&(?:nbsp|amp|quot|lt|gt|#\d+);"
    r"|\b(?:undefined|null|NaN|Infinity)\b"
)


# --- ophalen ---------------------------------------------------------------

def haal_op(url, pauze=0.0):
    """Haalt een URL op met een herkenbare User-Agent."""
    if pauze:
        time.sleep(pauze)
    verzoek = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(verzoek, timeout=30) as antwoord:
        ruw = antwoord.read()
    return ruw.decode("utf-8", errors="replace")


def lees_sitemap(url, pauze):
    """Geeft de URL's uit een sitemap terug, in volgorde van het bestand."""
    xml = haal_op(url, pauze)
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


def alle_sitemap_urls(pauze, index=SITEMAP_INDEX):
    """Alle pagina-URL's van de site, uit de sitemap-index en de sitemaps daarin."""
    urls = []
    for url in lees_sitemap(index, pauze):
        if url.endswith(".xml"):
            urls.extend(alle_sitemap_urls(pauze, url))
        else:
            urls.append(url)
    return urls


def valt_onder(url, pad):
    """Of een URL onder `pad` valt: het pad zelf, of alles erachter."""
    eigen = urllib.parse.urlparse(url).path.rstrip("/")
    return eigen == pad or eigen.startswith(pad + "/")


def urls_van_deel(urls, deel):
    """De URL's van één deel van de site, zonder dubbelen, in volgorde van de sitemaps."""
    return list(dict.fromkeys(url for url in urls if valt_onder(url, DELEN[deel])))


def naar_patroon(pad):
    """Zet een robots-pad ('/api/*', '/zoeken?*') om in een reguliere expressie."""
    patroon = re.escape(pad).replace(r"\*", ".*")
    if patroon.endswith(r"\$"):
        patroon = patroon[:-2] + "$"
    return re.compile("^" + patroon)


def maak_robots_controle():
    """Leest robots.txt en geeft een functie terug die zegt of een URL mag.

    Dit doen we zelf en niet met urllib.robotparser: die behandelt de ster in
    'Disallow: /api/*' als een gewoon teken, waardoor zo'n regel niets blokkeert.
    """
    try:
        tekst = haal_op(f"{SITE}/robots.txt")
    except Exception as fout:  # zonder robots.txt crawlen we niet
        sys.exit(f"Kan robots.txt niet lezen ({fout}). Gestopt uit voorzorg.")

    regels = []  # (lengte, mag_wel, patroon)
    geldt_voor_ons = False
    for regel in tekst.splitlines():
        regel = regel.split("#")[0].strip()
        sleutel, _, waarde = regel.partition(":")
        sleutel, waarde = sleutel.strip().lower(), waarde.strip()
        if sleutel == "user-agent":
            geldt_voor_ons = waarde == "*"
        elif geldt_voor_ons and sleutel in ("disallow", "allow") and waarde:
            regels.append((len(waarde), sleutel == "allow", naar_patroon(waarde)))

    verboden = [w for lengte, mag, w in regels if not mag]
    print(f"robots.txt: {len(verboden)} verboden pad(en) voor iedereen.")

    def mag_ophalen(url):
        onderdelen = urllib.parse.urlsplit(url)
        pad = onderdelen.path + (f"?{onderdelen.query}" if onderdelen.query else "")
        # De langste regel die past, wint; bij gelijke lengte wint 'Allow'.
        passend = [(lengte, mag) for lengte, mag, patroon in regels if patroon.match(pad)]
        if not passend:
            return True
        return max(passend, key=lambda r: (r[0], r[1]))[1]

    return mag_ophalen


# --- tekst uit de pagina halen ---------------------------------------------

def tekst_uit_main(pagina_html):
    """Haalt de leesbare tekst uit het <main>-element.

    Alles buiten <main> (menu, voettekst, cookiemelding) blijft buiten beeld:
    dat is geen redactionele content en zou alleen ruis opleveren.
    """
    treffer = re.search(r"<main\b[^>]*>(.*?)</main>", pagina_html, re.S | re.I)
    if not treffer:
        return ""
    inhoud = treffer.group(1)
    inhoud = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", inhoud, flags=re.S | re.I)
    inhoud = re.sub(r"<[^>]+>", " ", inhoud)
    inhoud = html.unescape(inhoud)
    return re.sub(r"\s+", " ", inhoud).strip()


def titel_uit(pagina_html):
    treffer = re.search(r"<title[^>]*>(.*?)</title>", pagina_html, re.S | re.I)
    if not treffer:
        return ""
    return re.sub(r"\s+", " ", html.unescape(treffer.group(1))).strip()


# --- spelling toetsen ------------------------------------------------------

def lees_woordenlijst(pad):
    woorden = set()
    with open(pad, encoding="utf-8") as bestand:
        for regel in bestand:
            woord = regel.strip()
            if woord and not woord.startswith("#"):
                woorden.add(woord)
                woorden.add(woord.lower())
    return woorden


def lees_goedgekeurd(pad):
    """De goedgekeurde woorden en namen, kleine letters. Dit is de enige lijst.

    Komt uit goedgekeurd.json, dat de workflow vlak voor de crawl uit de tabel
    `goedgekeurd` in Supabase haalt (scripts/haal_goedgekeurd.py). Ontbreekt het
    bestand, dan is er niets goedgekeurd. Namen en woorden gaan in dezelfde set: een
    goedgekeurde naam is ook goed aan het begin van een zin.
    """
    pad = Path(pad)
    if not pad.exists():
        return set()
    return {rij["woord"].lower() for rij in json.loads(pad.read_text(encoding="utf-8"))}


def verplaats_namen(bevindingen, verplaatst):
    """Namen die de redactie als verkeerd gespeld heeft aangewezen, tellen als spelfout.

    `verplaatst` is een set kleine letters (zie lees_goedgekeurd). De bevinding verliest zijn
    plaatsoordeel niet: dat wordt pas daarna bepaald en alleen voor wat nog een naam is.
    Geeft het aantal verplaatste bevindingen terug.
    """
    aantal = 0
    for bevinding in bevindingen:
        if bevinding["soort"] == "naam" and bevinding["woord"].lower() in verplaatst:
            bevinding["soort"] = "spelfout"
            aantal += 1
    return aantal


def is_bekend(woord, woorden):
    """Bekend als het woord in de lijst staat, of als alle delen dat doen.

    Het tweede geval vangt samenstellingen met een koppelteken of apostrof
    ('consulaat-generaal', 'euro's') die niet altijd los in de lijst staan.
    """
    if woord in woorden or woord.lower() in woorden:
        return True
    # Meervoud of bezit met een apostrof: "radiotaxi's", "foto's". Het losse
    # deel "s" is geen woord, dus toetsen we het woord zonder die uitgang.
    zonder_s = re.sub(r"['’]s$", "", woord)
    if zonder_s != woord and zonder_s.lower() in woorden:
        return True
    delen = [deel for deel in re.split(r"[-'’]", woord) if deel]
    if len(delen) > 1 and all(deel.lower() in woorden for deel in delen):
        return True
    return False


def is_plakfout(woord):
    """Zegt of een punt middenin het woord op een vergeten spatie wijst.

    "demonstraties.Volg het nieuws" is een echte redactionele fout. Een
    webadres ("Windy.com") en een afkorting ("U.S") zijn dat niet.
    """
    delen = [deel for deel in woord.split(".") if deel]
    if len(delen) < 2:
        return False
    if woord.lower().endswith(DOMEINEN):
        return False
    return not all(len(deel) == 1 for deel in delen)


def soort_van(woord, zin):
    """Deelt een bevinding in: 'spelfout' of 'naam'.

    Een hoofdletter middenin een zin duidt vrijwel altijd op een naam: een
    plaats, een organisatie of een anderstalige bron. Op reisadviespagina's is
    dat het leeuwendeel van de meldingen. We gooien ze niet weg maar zetten ze
    apart, zodat de echte spelfouten er niet in verdwijnen.

    Aan het zinsbegin zegt een hoofdletter niets, dus daar toetsen we gewoon
    door - zo blijft "Registeer" een spelfout. En een vergeten spatie gaat
    voor: "III.Let op dat u" begint met een hoofdletter maar is geen naam.

    De regel is met opzet uit te leggen aan een redacteur. Wie hem anders wil,
    verandert hem hier; de indeling staat in resultaten.json, dus het scherm
    is om te gooien zonder opnieuw te crawlen.
    """
    if is_plakfout(woord):
        return "spelfout"
    begin = zin.lstrip("“‘'\"([ ")
    if woord[:1].isupper() and not begin.startswith(woord):
        return "naam"
    return "spelfout"


def zoek_fouten(tekst, toegestaan):
    """Geeft per onbekend woord een bevinding met de zin eromheen.

    `toegestaan` is de woordenlijst en de goedgekeurde woorden bij elkaar. Door ze
    samen te nemen klopt ook een samenstelling die beide combineert, zoals
    "lhbtiq+-vriendelijke": het eerste deel komt uit onze eigen lijst, het
    tweede uit de woordenlijst.
    """
    bevindingen = []
    gezien = set()
    for zin in re.split(r"(?<=[.!?])\s+", tekst):
        # Eerst de sjabloonresten, en meteen in `gezien`: staat er "undefined",
        # dan meldt de woordenloop hieronder hem niet nog een tweede keer.
        for rest in SJABLOONRESTEN.findall(zin):
            sleutel = (rest, zin)
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            bevindingen.append({"woord": rest, "soort": "spelfout",
                                "context": kort(zin)})
        # De gevonden resten knippen we uit de zin voordat we hem in woorden
        # opdelen. Anders meldt de app "de&nbsp;grens" nog een keer naast het
        # "&nbsp;" dat er de oorzaak van is. De zin zelf blijft heel: die gaat
        # ongewijzigd als context mee.
        for ruw in SPLITSERS.split(SJABLOONRESTEN.sub(" ", zin)):
            woord = ruw.translate(ONZICHTBAAR).replace("’", "'").strip(LEESTEKENS)
            if not woord or not any(teken.isalpha() for teken in woord):
                continue
            if any(teken.isdigit() for teken in woord):
                continue  # versienummers, jaartallen, codes
            if "@" in woord:
                continue  # e-mailadressen
            if is_bekend(woord, toegestaan):
                continue
            sleutel = (woord, zin)
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            bevindingen.append({"woord": woord, "soort": soort_van(woord, zin),
                                "context": kort(zin)})
    return bevindingen


def kort(zin, lengte=200):
    return zin if len(zin) <= lengte else zin[: lengte - 1].rstrip() + "…"


# --- de crawl zelf ---------------------------------------------------------

def verzamel_paginas(bron, max_paginas, pauze, bij_totaal=lambda n: None):
    """Geeft (naam, html) per pagina, plus de URL's die we hebben overgeslagen.

    `bij_totaal` krijgt het aantal pagina's dat we verwachten te bekijken, zodra dat
    bekend is. Daar hangt de voortgangsbalk in het scherm aan.
    """
    overgeslagen = []

    if bron == "demo":
        paden = sorted((WORTEL / "demo").glob("*.html"))[:max_paginas]
        bij_totaal(len(paden))
        for pad in paden:
            yield f"demo/{pad.name}", pad.read_text(encoding="utf-8")
        return overgeslagen

    mag_ophalen = maak_robots_controle()
    alle = alle_sitemap_urls(0)
    urls = urls_van_deel(alle, bron)
    print(f"Deel {bron} ({DELEN[bron]}): {len(urls)} van de {len(alle)} URL's in de sitemaps.")
    if not urls:
        sys.exit(f"Geen enkele URL onder {DELEN[bron]} in de sitemaps. Is de site verbouwd? "
                 f"Controleer {SITEMAP_INDEX}.")
    bij_totaal(min(len(urls), max_paginas))

    opgehaald = 0
    for url in urls:
        if opgehaald >= max_paginas:
            break
        if not mag_ophalen(url):
            overgeslagen.append(url)
            print(f"  overgeslagen (robots.txt): {url}")
            continue
        try:
            yield url, haal_op(url, pauze)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as fout:
            overgeslagen.append(url)
            print(f"  overgeslagen (fout: {fout}): {url}")
            continue
        opgehaald += 1
        print(f"  [{opgehaald}/{max_paginas}] {url}")

    return overgeslagen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bron", default="demo",
                        choices=["demo", *DELEN], help="welk deel van de site")
    parser.add_argument("--max-paginas", type=int, default=5000,
                        help="harde bovengrens op het aantal pagina's (standaard 5000: een heel deel)")
    parser.add_argument("--woordenlijst", default=str(WORTEL / "data" / "woordenlijst.txt"))
    parser.add_argument("--goedgekeurd", default=str(WORTEL / "goedgekeurd.json"),
                        help="JSON met de in het scherm goedgekeurde woorden en namen")
    parser.add_argument("--naam-is-spelfout", default=str(WORTEL / "naam_is_spelfout.json"),
                        help="JSON met namen die als spelfout zijn aangewezen")
    parser.add_argument("--plaatsnamen", default=str(WORTEL / "data" / "geonames"),
                        help="map met de GeoNames-bestanden; zonder die map krijgen namen "
                             "geen oordeel over hun spelling")
    parser.add_argument("--aanvraag-id", default="",
                        help="id van de aanvraag in Supabase, voor de voortgangsbalk; "
                             "zonder dit meldt de crawl geen voortgang")
    parser.add_argument("--uit", default=str(WORTEL / "resultaten.json"))
    parser.add_argument("--pauze", type=float, default=0.5,
                        help="seconden wachten tussen twee pagina's")
    argumenten = parser.parse_args()

    lijst_pad = Path(argumenten.woordenlijst)
    if not lijst_pad.exists():
        reserve = WORTEL / "data" / "woordenlijst-demo.txt"
        print(f"LET OP: {lijst_pad} ontbreekt. Ik gebruik de kleine testlijst "
              f"{reserve.name}; die is alleen bedoeld voor de demo-pagina's.")
        lijst_pad = reserve
    woorden = lees_woordenlijst(lijst_pad)
    goedgekeurd = lees_goedgekeurd(argumenten.goedgekeurd)
    toegestaan = woorden | goedgekeurd
    print(f"Woordenlijst: {lijst_pad.name} ({len(woorden)} vormen), "
          f"{len(goedgekeurd)} goedgekeurde woorden en namen.")
    if argumenten.bron != "demo" and not goedgekeurd:
        print("LET OP: er zijn geen goedgekeurde woorden. Een gewone crawl heeft er honderden; "
              "zonder die lijst staan ze allemaal als fout in het resultaat.")

    bevindingen = []
    aantal_paginas = 0
    totaal = 0

    def totaal_bekend(aantal):
        nonlocal totaal
        totaal = aantal
        meld(argumenten.aanvraag_id, status="crawlen", paginas_klaar=0,
             paginas_totaal=aantal, run_url=run_url(),
             crawl_gestart_op=datetime.now(timezone.utc).isoformat(timespec="seconds"))

    paginas = verzamel_paginas(argumenten.bron, argumenten.max_paginas, argumenten.pauze,
                               totaal_bekend)
    overgeslagen = []
    while True:
        try:
            url, pagina_html = next(paginas)
        except StopIteration as einde:
            overgeslagen = einde.value or []
            break
        aantal_paginas += 1
        # Niet na elke pagina melden: dat zijn honderden verzoeken voor niets.
        if aantal_paginas % 5 == 0 or aantal_paginas == totaal:
            meld(argumenten.aanvraag_id, paginas_klaar=aantal_paginas)
        tekst = tekst_uit_main(pagina_html)
        if not tekst:
            print(f"  geen <main> gevonden: {url}")
            continue
        titel = titel_uit(pagina_html)
        for bevinding in zoek_fouten(tekst, toegestaan):
            bevindingen.append({"url": url, "titel": titel, **bevinding})

    verplaatst = verplaats_namen(bevindingen, lees_goedgekeurd(argumenten.naam_is_spelfout))
    if verplaatst:
        print(f"{verplaatst} bevindingen van namen die de redactie als spelfout heeft aangewezen.")

    # Een hulp, geen voorwaarde: een kapotte of onvolledige download mag de crawl niet laten falen.
    try:
        plaatsen = Plaatsnamen.laad(argumenten.plaatsnamen)
    except (OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as fout:
        print(f"::warning::De plaatsnamenlijst is onbruikbaar ({fout}); namen krijgen geen oordeel.")
        plaatsen = None
    if plaatsen is None:
        print(f"Geen plaatsnamenlijst in {argumenten.plaatsnamen}: namen krijgen geen oordeel.")
    else:
        for bevinding in bevindingen:
            if bevinding["soort"] == "naam":
                bevinding.update(plaatsen.beoordeel(bevinding["woord"]))
        print(samenvatting(bevindingen))

    resultaat = {
        "gestart_op": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bron": argumenten.bron,
        "woordenlijst": lijst_pad.name,
        "user_agent": USER_AGENT,
        "aantal_paginas": aantal_paginas,
        "aantal_bevindingen": len(bevindingen),
        "aantal_spelfouten": sum(1 for b in bevindingen if b["soort"] == "spelfout"),
        "aantal_namen": sum(1 for b in bevindingen if b["soort"] == "naam"),
        "overgeslagen_urls": overgeslagen,
        "bevindingen": bevindingen,
    }
    uit = Path(argumenten.uit)
    uit.parent.mkdir(parents=True, exist_ok=True)
    uit.write_text(json.dumps(resultaat, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"\n{aantal_paginas} pagina's bekeken, {len(bevindingen)} bevindingen "
          f"({resultaat['aantal_spelfouten']} spelfouten, "
          f"{resultaat['aantal_namen']} namen) -> {uit}")


if __name__ == "__main__":
    main()
