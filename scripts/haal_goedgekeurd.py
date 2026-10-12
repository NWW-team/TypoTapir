#!/usr/bin/env python3
"""Haalt de lijsten op die de redactie in het scherm bijhoudt, uit Supabase.

Schrijft twee bestanden, die crawl.py leest:
  goedgekeurd.json       woorden en namen die goed zijn (tabel `goedgekeurd`)
  naam_is_spelfout.json  namen die de redactie als verkeerd gespeld heeft aangewezen en die dus
                         bij de spelfouten horen (tabel `naam_is_spelfout`)
 Draait op de GitHub-runner vlak
voor de crawl. Alleen de standaardbibliotheek van Python.

Dit is de enige lijst met goedgekeurde woorden. Lukt het ophalen niet, dan stopt de
run: een crawl zonder die lijst meldt honderden goede woorden als fout, en dat resultaat
komt dan in het scherm als ware het een gewone crawl.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORTEL = Path(__file__).resolve().parent.parent
BLOK = 1000  # PostgREST geeft er standaard niet meer dan duizend per verzoek


def haal(basis, sleutel, tabel="goedgekeurd", kolommen="woord,soort", actief="ingetrokken_op"):
    """Alle actieve rijen van een tabel. `actief` is de kolom die leeg is zolang de rij geldt."""
    rijen = []
    for van in range(0, 10**9, BLOK):
        aanvraag = urllib.request.Request(
            f"{basis}/rest/v1/{tabel}?select={kolommen}&{actief}=is.null"
            f"&order=id&limit={BLOK}&offset={van}",
            headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}"})
        with urllib.request.urlopen(aanvraag, timeout=60) as antwoord:
            blok = json.loads(antwoord.read().decode("utf-8"))
        rijen.extend(blok)
        if len(blok) < BLOK:
            return rijen


def main():
    uit = Path(sys.argv[1]) if len(sys.argv) > 1 else WORTEL / "goedgekeurd.json"
    uit_verplaatst = uit.with_name("naam_is_spelfout.json")
    basis = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sleutel = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not basis or not sleutel:
        sys.exit("SUPABASE_URL of SUPABASE_SERVICE_ROLE_KEY ontbreekt, dus ik kan de "
                 "goedgekeurde woorden niet ophalen.")
    try:
        rijen = haal(basis, sleutel)
        verplaatst = haal(basis, sleutel, "naam_is_spelfout", "woord", "teruggezet_op")
    except (urllib.error.URLError, TimeoutError, ValueError) as fout:
        sys.exit(f"De lijsten van de redactie ophalen mislukte ({fout}). De crawl stopt: zonder "
                 f"die lijsten zou het resultaat vol staan met woorden die goed zijn, of met "
                 f"namen die op de verkeerde plek staan.")
    uit.write_text(json.dumps(rijen, ensure_ascii=False), encoding="utf-8")
    uit_verplaatst.write_text(json.dumps(verplaatst, ensure_ascii=False), encoding="utf-8")
    print(f"{len(verplaatst)} namen als spelfout aangewezen -> {uit_verplaatst}")
    woorden = sum(1 for r in rijen if r["soort"] == "woord")
    print(f"{len(rijen)} goedgekeurd ({woorden} woorden, {len(rijen) - woorden} namen) -> {uit}")


if __name__ == "__main__":
    main()
