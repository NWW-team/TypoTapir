#!/usr/bin/env python3
"""Zet het resultaat van een crawl in Supabase, achter de toegangscontrole.

Vervangt het oude gedrag waarbij docs/resultaten.json in deze publieke
repository werd gecommit en dus voor iedereen te lezen was.

Draait op de GitHub-runner, niet in de browser. De sleutel komt uit de
omgeving en hoort in een GitHub Actions secret:

    SUPABASE_URL                de project-URL, bijvoorbeeld
                                https://xxxxxxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY   de service-role key

Die key zet RLS buiten werking en mag daarom nergens anders staan: niet in de
frontend, niet in deze repository en niet in een prompt. Alleen de
standaardbibliotheek van Python, zoals de rest van dit project.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from voortgang import meld

WORTEL = Path(__file__).resolve().parent.parent

# Per verzoek uploaden we een blok bevindingen. Groot genoeg om niet honderden
# verzoeken te doen, klein genoeg om niet op een limiet te stuiten.
BLOK = 500

# Deze velden komen één-op-één uit resultaten.json in de tabel crawls. De
# aantallen (aantal_bevindingen en zo) staan er niet bij: die zijn uit de
# bevindingen zelf te tellen, en twee keer opslaan levert alleen de kans op dat
# ze ooit niet meer overeenkomen.
CRAWL_VELDEN = ("gestart_op", "bron", "woordenlijst", "user_agent",
                "aantal_paginas", "overgeslagen_urls")


def verzoek(basis, sleutel, pad, lichaam, extra_kop=None):
    data = json.dumps(lichaam, ensure_ascii=False).encode("utf-8")
    kop = {
        "apikey": sleutel,
        "Authorization": f"Bearer {sleutel}",
        "Content-Type": "application/json",
    }
    if extra_kop:
        kop.update(extra_kop)
    aanvraag = urllib.request.Request(f"{basis}/rest/v1/{pad}", data=data,
                                      headers=kop, method="POST")
    try:
        with urllib.request.urlopen(aanvraag, timeout=60) as antwoord:
            rauw = antwoord.read().decode("utf-8")
            return json.loads(rauw) if rauw.strip() else None
    except urllib.error.HTTPError as fout:
        # De melding van Supabase erbij, anders sta je naar een 400 te kijken
        # zonder te weten welk veld er niet klopt. De sleutel zelf staat niet in
        # de melding, en die mag ook niet in een logboek belanden.
        melding = fout.read().decode("utf-8", "replace")[:800]
        sys.exit(f"Supabase gaf {fout.code} op {pad}: {melding}")
    except urllib.error.URLError as fout:
        sys.exit(f"Kan {basis} niet bereiken: {fout.reason}")


def rol_uit_jwt(sleutel):
    """De rol uit een JWT-sleutel, of None als het er geen is.

    Een JWT is base64; de rol staat er niet leesbaar in. Een sleutel van het
    nieuwe formaat (sb_secret_...) is geen JWT en levert None op.
    """
    delen = sleutel.split(".")
    if len(delen) != 3:
        return None
    lading = delen[1]
    try:
        opvulling = "=" * (-len(lading) % 4)
        ruw = base64.urlsafe_b64decode(lading + opvulling)
        return json.loads(ruw).get("role")
    except Exception:
        return None


def controleer_sleutel(sleutel):
    """Zegt het meteen als dit geen sleutel is, in plaats van een kale 401.

    Twee keer eerder misgegaan: het label `service_role` uit het dashboard
    gekopieerd in plaats van de sleutel ernaast, en de publishable key gebruikt
    die geen schrijfrechten heeft.
    """
    if sleutel.startswith("sb_publishable_") or rol_uit_jwt(sleutel) == "anon":
        sys.exit("Dit is de publishable key of de anon key, niet de service-role "
                 "key. Die eerste mag publiek zijn en mag niets schrijven. Pak in "
                 "het Supabase-dashboard onder Project Settings > API Keys de "
                 "geheime sleutel.")

    lijkt_op_jwt = sleutel.count(".") == 2 and sleutel.startswith("eyJ")
    lijkt_op_secret = sleutel.startswith("sb_secret_")
    if not (lijkt_op_jwt or lijkt_op_secret):
        sys.exit(f"De waarde in SUPABASE_SERVICE_ROLE_KEY is {len(sleutel)} tekens "
                 f"lang en ziet niet uit als een sleutel. Verwacht is een lange "
                 f"tekst die begint met 'eyJ' of 'sb_secret_'. Let op: in het "
                 f"dashboard staat het woord 'service_role' naast de sleutel; je "
                 f"hebt de sleutel nodig, niet dat label. Gebruik de kopieerknop.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="bestand",
                        default=str(WORTEL / "resultaten.json"),
                        help="het JSON-bestand dat crawl.py heeft geschreven")
    parser.add_argument("--aanvraag-id", default="",
                        help="id van de aanvraag in Supabase, voor de voortgangsbalk")
    argumenten = parser.parse_args()

    basis = os.environ.get("SUPABASE_URL", "").rstrip("/")
    # .strip(): een sleutel die via de klembord in een secret is geplakt sleept
    # makkelijk een newline mee, en dan is hij ongeldig zonder dat je ziet waarom.
    sleutel = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not basis or not sleutel:
        sys.exit("SUPABASE_URL en SUPABASE_SERVICE_ROLE_KEY moeten in de "
                 "omgeving staan. Zet ze als GitHub Actions secret.")
    controleer_sleutel(sleutel)

    pad = Path(argumenten.bestand)
    if not pad.exists():
        sys.exit(f"{pad} bestaat niet. Draai eerst scripts/crawl.py.")
    resultaat = json.loads(pad.read_text(encoding="utf-8"))

    bevindingen = resultaat.get("bevindingen", [])
    if not bevindingen:
        print("Geen bevindingen in het bestand; er wordt niets gepubliceerd.")
        meld(argumenten.aanvraag_id, status="klaar")
        return

    meld(argumenten.aanvraag_id, status="publiceren")

    crawl_rij = {veld: resultaat[veld] for veld in CRAWL_VELDEN if veld in resultaat}
    gemaakt = verzoek(basis, sleutel, "crawls", crawl_rij,
                      {"Prefer": "return=representation"})
    crawl_id = gemaakt[0]["id"]
    print(f"Crawl aangemaakt: {crawl_id} ({crawl_rij.get('bron')}, "
          f"{crawl_rij.get('aantal_paginas')} pagina's)")

    verstuurd = 0
    for begin in range(0, len(bevindingen), BLOK):
        blok = [{
            "crawl_id": crawl_id,
            "url": b["url"],
            "titel": b.get("titel"),
            "woord": b["woord"],
            # Een oudere crawl kende het onderscheid nog niet; die bevindingen
            # zijn spelfouten, want zo stonden ze toen ook in het scherm.
            "soort": b.get("soort", "spelfout"),
            "context": b.get("context"),
            # Alleen bij namen, en alleen als de plaatsnamenlijst beschikbaar was.
            "plaats_status": b.get("plaats_status"),
            "suggestie": b.get("suggestie"),
        } for b in bevindingen[begin:begin + BLOK]]
        verzoek(basis, sleutel, "bevindingen", blok,
                {"Prefer": "return=minimal"})
        verstuurd += len(blok)
        print(f"  {verstuurd}/{len(bevindingen)} bevindingen geplaatst")

    meld(argumenten.aanvraag_id, status="klaar")
    print(f"\nKlaar. {verstuurd} bevindingen staan in Supabase.")


if __name__ == "__main__":
    main()
