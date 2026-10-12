#!/usr/bin/env python3
"""Controles voor SpellingSpeurneus.

    python3 scripts/test.py          # alles, inclusief robots.txt (netwerk nodig)
    python3 scripts/test.py --offline  # alleen de controles zonder netwerk
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plaatsnamen import Plaatsnamen, afstand, samenvatting, tokens  # noqa: E402
from voortgang import meld  # noqa: E402
from crawl import (DELEN, SITE, alle_sitemap_urls, is_bekend, urls_van_deel, valt_onder, verplaats_namen, lees_goedgekeurd,  # noqa: E402
                   maak_robots_controle, naar_patroon, soort_van, tekst_uit_main,
                   zoek_fouten)

WORTEL = Path(__file__).resolve().parent.parent
uitkomsten = []


def controle(naam, gelukt, toelichting=""):
    uitkomsten.append(gelukt)
    print(f"  {'OK  ' if gelukt else 'FOUT'} {naam}" + (f" — {toelichting}" if toelichting else ""))


def _faalt(functie):
    """True als de functie een fout gooit (hier: een ongeldig id)."""
    try:
        functie()
    except Exception:
        return True
    return False


def draai_crawl(uitvoer, goedgekeurd=None):
    # Zonder --goedgekeurd zoekt crawl.py naar een goedgekeurd.json in de wortel
    # van de repository. Wijs daarom altijd een bestand aan, zodat een los
    # achtergebleven bestand de controles niet beinvloedt.
    opdracht = [sys.executable, str(WORTEL / "scripts" / "crawl.py"),
                "--bron", "demo", "--max-paginas", "5", "--uit", str(uitvoer),
                "--goedgekeurd", str(goedgekeurd or "bestaat-niet.json"),
                "--naam-is-spelfout", "bestaat-niet.json"]
    subprocess.run(opdracht, check=True, capture_output=True)
    return json.loads(Path(uitvoer).read_text(encoding="utf-8"))


def main():
    offline = "--offline" in sys.argv
    tijdelijk = Path(tempfile.mkdtemp())

    def woorden_in(zin):
        return [b["woord"] for b in zoek_fouten(zin, set())]

    def woorden_in_met(zin, toegestaan):
        return [b["woord"] for b in zoek_fouten(zin, toegestaan)]


    print("De drie ingebouwde fouten in demo/")
    resultaat = draai_crawl(tijdelijk / "demo.json")
    gevonden = {b["woord"] for b in resultaat["bevindingen"]}
    for fout in ("aanvraeg", "gelegenhied", "buitenladn"):
        controle(f"{fout} gevonden", fout in gevonden)
    controle("geen andere meldingen", len(gevonden) == 3, f"gevonden: {sorted(gevonden)}")
    controle("alle drie gelden als spelfout, niet als naam",
             all(b["soort"] == "spelfout" for b in resultaat["bevindingen"]))

    print("\nAlleen <main> wordt gelezen")
    for nepwoord in ("kwaliteitt", "navigatiefoutt", "voetfoutt"):
        controle(f"{nepwoord} uit menu/voettekst genegeerd", nepwoord not in gevonden)

    print("\nIn het scherm goedgekeurd")
    gk = tijdelijk / "goedgekeurd.json"
    gk.write_text(json.dumps([{"woord": "aanvraeg", "soort": "woord"},
                              {"woord": "Cochabamba", "soort": "naam"}]), encoding="utf-8")
    na_goedkeuren = draai_crawl(tijdelijk / "gk.json", goedgekeurd=gk)
    over = {b["woord"] for b in na_goedkeuren["bevindingen"]}
    controle("goedgekeurd woord verdwijnt", "aanvraeg" not in over)
    controle("de rest blijft staan", over == {"gelegenhied", "buitenladn"}, f"over: {sorted(over)}")
    toegestaan = lees_goedgekeurd(gk) | {"reis", "naar", "of"}
    controle("goedgekeurde naam verdwijnt, ook met andere hoofdletters",
             woorden_in_met("Reis naar Cochabamba of COCHABAMBA.", toegestaan) == [])
    controle("een andere naam blijft gemeld",
             woorden_in_met("Reis naar Cochabambo.", toegestaan) == ["Cochabambo"])
    controle("zonder bestand is er niets goedgekeurd",
             lees_goedgekeurd(tijdelijk / "bestaat-niet.json") == set())

    print("\nVoortgang melden")
    ontvangen = []

    class Nepsupabase(BaseHTTPRequestHandler):
        def do_PATCH(self):
            lengte = int(self.headers.get("Content-Length", 0))
            ontvangen.append((self.path, json.loads(self.rfile.read(lengte)),
                              self.headers.get("apikey")))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Nepsupabase)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    oud_omgeving = {k: os.environ.get(k) for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}
    try:
        os.environ["SUPABASE_URL"] = f"http://127.0.0.1:{server.server_port}"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "sleutel"
        controle("een melding geeft True", meld("12", status="crawlen", paginas_klaar=5) is True)
        pad, lichaam, apikey = ontvangen[-1]
        controle("de melding gaat naar de juiste rij", "/crawl_aanvragen?id=eq.12" in pad, pad)
        controle("een gestopte of mislukte aanvraag wordt niet meer bijgewerkt",
                 "status=in.(aangevraagd,crawlen,publiceren)" in pad, pad)
        controle("de velden komen aan, plus een tijdstip",
                 lichaam["status"] == "crawlen" and lichaam["paginas_klaar"] == 5
                 and "bijgewerkt_op" in lichaam)
        controle("de sleutel gaat mee als apikey", apikey == "sleutel")
        voor = len(ontvangen)
        controle("zonder aanvraag-id wordt niets gemeld",
                 meld("", status="klaar") is False and len(ontvangen) == voor)
        controle("een id met rommel wordt geweigerd, niet doorgegeven",
                 _faalt(lambda: meld("1;drop", status="klaar")) and len(ontvangen) == voor)
        # Een crawl met aanvraag-id draait door en meldt zijn tellingen
        ontvangen.clear()
        subprocess.run([sys.executable, str(WORTEL / "scripts" / "crawl.py"), "--bron", "demo",
                        "--max-paginas", "5", "--uit", str(tijdelijk / "v.json"),
                        "--goedgekeurd", "bestaat-niet.json", "--aanvraag-id", "7"],
                       check=True, capture_output=True, env=os.environ.copy())
        statussen = [m[1] for m in ontvangen]
        controle("de crawl meldt eerst het totaal",
                 statussen and statussen[0].get("status") == "crawlen"
                 and statussen[0].get("paginas_totaal") == 5, f"{statussen[:1]}")
        controle("de crawl meldt zijn laatste stand",
                 statussen[-1].get("paginas_klaar") == 5, f"{statussen[-1:]}")
        # De workflow legt als eerste de link naar de run vast, zodat de crawl te stoppen is
        ontvangen.clear()
        subprocess.run([sys.executable, str(WORTEL / "scripts" / "voortgang.py"), "--id", "7",
                        "--status", "gestart"], check=True, capture_output=True,
                       env={**os.environ, "GITHUB_SERVER_URL": "https://github.com",
                            "GITHUB_REPOSITORY": "NWW-team/SpellingSpeurneus", "GITHUB_RUN_ID": "555"})
        controle("gestart legt alleen de link naar de run vast",
                 ontvangen and ontvangen[0][1].get("run_url") ==
                 "https://github.com/NWW-team/SpellingSpeurneus/actions/runs/555"
                 and "status" not in ontvangen[0][1], str(ontvangen[:1]))
        os.environ["SUPABASE_URL"] = "http://127.0.0.1:1"
        controle("een onbereikbare server stopt niets, het geeft False",
                 meld("12", status="crawlen") is False)
    finally:
        server.shutdown()
        for k, v in oud_omgeving.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("\nDelen van de site")
    controle("het pad zelf hoort erbij", valt_onder(SITE + "/reisadvies", "/reisadvies"))
    controle("alles daarachter hoort erbij", valt_onder(SITE + "/reisadvies/albanie", "/reisadvies"))
    controle("een slotstreep maakt niet uit", valt_onder(SITE + "/reisadvies/", "/reisadvies"))
    controle("een query telt niet mee", valt_onder(SITE + "/visum-nederland?a=1", "/visum-nederland"))
    controle("een ander pad met dezelfde beginletters hoort er niet bij",
             not valt_onder(SITE + "/reisadvies-iets", "/reisadvies"))
    controle("een ander deel hoort er niet bij", not valt_onder(SITE + "/visum-nederland/x", "/caribisch-visum"))
    controle("diep onderliggende pagina's horen erbij",
             valt_onder(SITE + "/contact/ambassades-consulaten-generaal/afghanistan/kabul",
                        "/contact/ambassades-consulaten-generaal"))
    controle("er zijn vier delen met de gevraagde paden",
             DELEN == {"reisadvies": "/reisadvies", "visum-nederland": "/visum-nederland",
                       "caribisch-visum": "/caribisch-visum",
                       "ambassades": "/contact/ambassades-consulaten-generaal"}, str(DELEN))
    voorbeeld = [SITE + p for p in ("/reisadvies/albanie", "/visum-nederland/schengenvisum",
                                     "/caribisch-visum/kort-verblijf/a", "/reisadvies/albanie",
                                     "/reisadvies", "/over-ons")]
    gevonden = urls_van_deel(voorbeeld, "reisadvies")
    controle("een deel kiest zijn pagina's, zonder dubbelen",
             gevonden == [SITE + "/reisadvies/albanie", SITE + "/reisadvies"], str(gevonden))

    # De sitemap-index en de sitemaps daarin, via een lokale nagemaakte server
    paginas = {
        "/sitemap.xml": "<sitemapindex><sitemap><loc>{b}/a.xml</loc></sitemap>"
                        "<sitemap><loc>{b}/b.xml</loc></sitemap></sitemapindex>",
        "/a.xml": "<urlset><url><loc>https://x.nl/visum-nederland/1</loc></url>"
                  "<url><loc>https://x.nl/reisadvies</loc></url></urlset>",
        "/b.xml": "<urlset><url><loc>https://x.nl/visum-nederland/2</loc></url></urlset>",
    }

    class Nepsite(BaseHTTPRequestHandler):
        def do_GET(self):
            tekst = paginas.get(self.path)
            self.send_response(200 if tekst else 404)
            self.end_headers()
            if tekst:
                self.wfile.write(tekst.format(b=f"http://127.0.0.1:{self.server.server_port}").encode())

        def log_message(self, *args):
            pass

    nepsite = HTTPServer(("127.0.0.1", 0), Nepsite)
    threading.Thread(target=nepsite.serve_forever, daemon=True).start()
    try:
        verzameld = alle_sitemap_urls(0, f"http://127.0.0.1:{nepsite.server_port}/sitemap.xml")
        controle("alle sitemaps uit de index worden gelezen", len(verzameld) == 3, str(verzameld))
        controle("de URL's van een deel komen uit meerdere sitemaps",
                 urls_van_deel(verzameld, "visum-nederland") ==
                 ["https://x.nl/visum-nederland/1", "https://x.nl/visum-nederland/2"])
    finally:
        nepsite.shutdown()

    print("\nPlaatsnamen beoordelen")
    # Een klein bestand in het echte GeoNames-formaat (tabs, 19 kolommen).
    import zipfile

    def stad(naam, ascii_naam, alt, inwoners):
        kolommen = ["1", naam, ascii_naam, alt, "0", "0", "P", "PPL", "XX", "", "", "", "", "",
                    str(inwoners), "", "", "", ""]
        return "\t".join(kolommen)

    kaarten = tijdelijk / "geonames"
    kaarten.mkdir()
    with zipfile.ZipFile(kaarten / "cities1000.zip", "w") as z:
        z.writestr("cities1000.txt", "\n".join([
            stad("Cochabamba", "Cochabamba", "Kochabamba,Cercado", 630000),
            stad("Córdoba", "Cordoba", "Cordova", 1300000),
            stad("Valparaíso", "Valparaiso", "", 280000),
            stad("La Paz", "La Paz", "", 790000),
            stad("Bukavu", "Bukavu", "", 800000),
            stad("Heath", "Heath", "", 2000),          # klein: bekend, geen suggestie
            stad("Tanguiéta", "Tanguieta", "", 12000),   # klein: bekend, geen suggestie
        ]))
    (kaarten / "admin1CodesASCII.txt").write_text(
        "CO.02\tAntioquia\tAntioquia\t1\nCD.10\tHaut-Mbomou\tHaut-Mbomou\t2\n", encoding="utf-8")
    (kaarten / "countryInfo.txt").write_text(
        "#ISO\tISO3\tNum\tFIPS\tCountry\tCapital\n"
        "BO\tBOL\t68\tBL\tBolivia\tSucre\n", encoding="utf-8")
    pl = Plaatsnamen.laad(kaarten)
    status = lambda naam: pl.beoordeel(naam)["plaats_status"]
    sugg = lambda naam: pl.beoordeel(naam)["suggestie"]
    controle("een bekende plaats is bekend", status("Cochabamba") == "bekend")
    controle("accenten tellen niet mee", status("Cordoba") == "bekend" and status("Córdoba") == "bekend")
    controle("een bekende alternatieve schrijfwijze is bekend", status("Kochabamba") == "bekend")
    controle("een plaats van meerdere woorden", status("La Paz") == "bekend")
    controle("een regio met koppelteken", status("Haut-Mbomou") == "bekend")
    controle("een land", status("Bolivia") == "bekend")
    controle("een kleine plaats is bekend", status("Tanguiéta") == "bekend")
    controle("één letter fout wordt twijfel, met suggestie",
             status("Cochabamva") == "twijfel" and sugg("Cochabamva") == "Cochabamba",
             str(pl.beoordeel("Cochabamva")))
    controle("omgewisselde letters tellen als één fout",
             sugg("Cochabmaba") == "Cochabamba", str(pl.beoordeel("Cochabmaba")))
    controle("de suggestie heeft zijn accenten", sugg("Valparasio") in (None, "Valparaíso")
             and sugg("Valparaisso") == "Valparaíso", str(pl.beoordeel("Valparaisso")))
    controle("een fout in een deel van een naam telt", status("Haut-Mbomuo") == "twijfel")
    controle("kleine plaatsen dienen niet als suggestie",
             status("Hearth") == "onbekend" and status("Tanguieta") == "bekend")
    controle("korte woorden krijgen geen suggestie", status("AOA") == "onbekend" and status("Cala") == "onbekend")
    controle("een woord dat nergens op lijkt is onbekend", status("Evercare") == "onbekend")
    controle("een naam zonder letters is onbekend", status("2024") == "onbekend")
    controle("zonder bestand geen oordeel", Plaatsnamen.laad(tijdelijk / "bestaat-niet") is None)
    controle("afstand telt een omwisseling als één", afstand("abcd", "abdc", 2) == 1)
    controle("afstand stopt boven de grens", afstand("abcdef", "uvwxyz", 1) == 2)
    controle("tokens splitsen op koppelteken en apostrof", tokens("Haut-Mbomou l'Ouest") == ["haut", "mbomou", "ouest"])
    gemeld = samenvatting([{"woord": "Cochabamva", "plaats_status": "twijfel", "suggestie": "Cochabamba"},
                           {"woord": "Cochabamva", "plaats_status": "twijfel", "suggestie": "Cochabamba"},
                           {"woord": "Bukavu", "plaats_status": "bekend", "suggestie": None}])
    controle("het logboek telt unieke namen", "1 bekend" in gemeld and "1 twijfel" in gemeld, gemeld)
    # Een kapot bestand mag de crawl niet laten falen
    kapot = tijdelijk / "kapot"
    kapot.mkdir()
    (kapot / "cities1000.zip").write_bytes(b"dit is geen zipbestand")
    kapot_run = subprocess.run(
        [sys.executable, str(WORTEL / "scripts" / "crawl.py"), "--bron", "demo", "--max-paginas", "5",
         "--uit", str(tijdelijk / "kapot.json"), "--goedgekeurd", "bestaat-niet.json",
         "--plaatsnamen", str(kapot)], capture_output=True, text=True)
    controle("een kapotte plaatsnamenlijst laat de crawl niet falen",
             kapot_run.returncode == 0 and "onbruikbaar" in kapot_run.stdout, kapot_run.stderr[-200:])
    # Een volledige crawl met de lijst eraan: spelfouten blijven zonder oordeel
    pl_run = draai_crawl(tijdelijk / "pl.json")
    controle("de crawl draait ook zonder plaatsnamenlijst",
             all("plaats_status" not in b for b in pl_run["bevindingen"]))

    print("\nEdge Functions (stoppen en verplaatsen)")
    # De logica staat los van Supabase en GitHub en draait onder Node (22.18 of nieuwer).
    import shutil
    node = shutil.which("node")

    def node_kan_typescript():
        # Zonder opties lezen kan Node 22.18 of nieuwer. Een oudere Node (of geen) slaat de
        # controle over: ze hoort een crawl nooit tegen te houden.
        try:
            versie = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
            hoofd, klein = (int(x) for x in versie.lstrip("v").split(".")[:2])
            return (hoofd, klein) >= (22, 18)
        except (ValueError, OSError):
            return False

    if node and node_kan_typescript():
        for functie, bestand in (("crawl-stoppen", "stoppen.test.ts"), ("naam-verplaatsen", "verplaatsen.test.ts")):
            uitkomst = subprocess.run([node, str(WORTEL / "supabase" / "functions" / functie / bestand)],
                                      capture_output=True, text=True)
            regels = [r for r in uitkomst.stdout.splitlines() if r.strip().startswith(("OK", "FOUT"))]
            controle(f"de {len(regels)} controles van {bestand} slagen",
                     uitkomst.returncode == 0 and len(regels) > 0 and not any("FOUT" in r for r in regels),
                     (uitkomst.stdout + uitkomst.stderr)[-300:] if uitkomst.returncode else "")
    else:
        print("  (Node 22.18 of nieuwer ontbreekt: de tests van de Edge Functions zijn overgeslagen)")

    print("\nExcel-bestand (docs/xlsx.js)")
    # We maken een bestand onder Node en lezen het met een gewone XML-lezer terug. Een echte
    # Excel of LibreOffice is hier niet te draaien, dus dit toetst de structuur: geldige XML,
    # verwijzingen die kloppen, stijlen die bestaan en tekst die tekst blijft.
    if node:
        import xml.etree.ElementTree as ET
        xl_pad = tijdelijk / "proef.xlsx"
        gelukt = subprocess.run([node, str(WORTEL / "scripts" / "xlsx_proef.js"), str(WORTEL / "docs" / "xlsx.js"), str(xl_pad)],
                                capture_output=True, text=True)
        controle("het bestand wordt gemaakt", gelukt.returncode == 0 and xl_pad.exists(), gelukt.stderr[-200:])
        z = zipfile.ZipFile(xl_pad)
        controle("de zip is heel (CRC's kloppen)", z.testzip() is None)
        namen_in_zip = [i.filename for i in z.infolist()]
        controle("[Content_Types].xml staat vooraan", namen_in_zip[0] == "[Content_Types].xml", str(namen_in_zip))
        controle("de bestanden zijn niet gecomprimeerd en hebben het UTF-8-teken",
                 all(i.compress_type == 0 and i.flag_bits & 0x800 for i in z.infolist()))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        bomen = {}
        for naam in namen_in_zip:
            bomen[naam] = ET.fromstring(z.read(naam))      # gooit bij ongeldige XML
        controle("alle onderdelen zijn geldige XML", len(bomen) == len(namen_in_zip))
        typen = {e.get("PartName") for e in bomen["[Content_Types].xml"] if e.get("PartName")}
        controle("elk onderdeel heeft een inhoudstype",
                 all(("/" + n) in typen for n in namen_in_zip if n.startswith("xl/") and n.endswith(".xml")
                     and "_rels" not in n), str(typen))
        doelen = [e.get("Target") for r in ("xl/_rels/workbook.xml.rels",) for e in bomen[r]]
        controle("de verwijzingen wijzen naar bestaande onderdelen",
                 all(("xl/" + d) in namen_in_zip for d in doelen), str(doelen))
        blad = bomen["xl/worksheets/sheet1.xml"]
        controle("de elementen staan in de volgorde die Excel eist",
                 [e.tag.split("}")[1] for e in blad] == ["sheetViews", "cols", "sheetData", "autoFilter"])
        werkbladnaam = bomen["xl/workbook.xml"].find(".//m:sheet", ns).get("name")
        controle("de werkbladnaam is geldig (geen : / [ ] en niet te lang)",
                 not any(t in werkbladnaam for t in ':\\/?*[]') and 0 < len(werkbladnaam) <= 31, werkbladnaam)
        aantal_stijlen = len(bomen["xl/styles.xml"].find("m:cellXfs", ns))
        cellen = list(blad.iter("{%s}c" % ns["m"]))
        controle("elke stijl die een cel noemt bestaat", all(int(c.get("s", 0)) < aantal_stijlen for c in cellen))
        controle("er staat geen formule in het bestand", not list(blad.iter("{%s}f" % ns["m"])))
        rijen_xml = list(blad.iter("{%s}row" % ns["m"]))
        controle("kopregel plus alle rijen, in volgorde",
                 [int(r.get("r")) for r in rijen_xml] == list(range(1, 307 + 1)), str(len(rijen_xml)))

        def tekst(rij_nr, kolom):
            for c in rijen_xml[rij_nr - 1]:
                if c.get("r") == f"{kolom}{rij_nr}":
                    t = c.find("m:is/m:t", ns)
                    return t.text if t is not None else c.find("m:v", ns).text
            return None
        controle("de kopregel klopt", [tekst(1, k) for k in "ABCD"] == ["Woord", "Zin", "Pagina", "Aantal"])
        controle("tekens als & < > \" blijven heel", tekst(2, "B") == 'Dat is nieet goed & <mooi> "zo".', tekst(2, "B"))
        controle("een getal blijft een getal", tekst(2, "D") == "3")
        controle("tekst die met = + @ begint blijft tekst",
                 tekst(3, "A") == "=1+1" and tekst(3, "C") == "+cmd" and tekst(3, "D") == "@som")
        controle("accenten en een emoji blijven heel", tekst(4, "A") == "Córdoba" and tekst(4, "B") == "Zürich 🌍 São")
        controle("een leeg veld geeft geen cel", tekst(4, "D") is None and tekst(4, "C") is None)
        controle("een besturingsteken wordt weggehaald", tekst(5, "A") == "metstuur", repr(tekst(5, "A")))
        controle("een regeleinde blijft staan", tekst(5, "B") == "regel een\nregel twee")
        controle("een te lange tekst wordt afgekapt op de celgrens van Excel", len(tekst(6, "B")) == 32767)
        controle("het filter loopt over de hele tabel",
                 blad.find("m:autoFilter", ns).get("ref") == "A1:D307")
        stukken = rijen_xml[306].findall("m:c", ns)[1].findall("m:is/m:r", ns)
        vet = [r.find("m:rPr/m:b", ns) is not None for r in stukken]
        controle("opgemaakte tekst: een stuk vet, de rest gewoon", vet == [False, True, False], str(vet))
        controle("opgemaakte tekst blijft samen de hele zin",
                 "".join(r.find("m:t", ns).text for r in stukken) == "Dat is nieet & <co goed.")
    else:
        print("  (Node ontbreekt: de controles op het Excel-bestand zijn overgeslagen)")

    print("\nNamen die als spelfout zijn aangewezen")
    bev = [{"woord": "Hairi", "soort": "naam"}, {"woord": "hairi", "soort": "naam"},
           {"woord": "Cochabamba", "soort": "naam"}, {"woord": "nieet", "soort": "spelfout"}]
    aantal = verplaats_namen(bev, {"hairi"})
    controle("een aangewezen naam wordt spelfout, ongeacht hoofdletters",
             aantal == 2 and [b["soort"] for b in bev] == ["spelfout", "spelfout", "naam", "spelfout"], str(bev))
    controle("zonder aanwijzingen verandert er niets", verplaats_namen([{"woord": "X", "soort": "naam"}], set()) == 0)
    controle("een gewone spelfout blijft zoals hij was", bev[3]["soort"] == "spelfout")

    print("\nDe lijsten van de redactie ophalen")
    uitgereikt = {"/rest/v1/goedgekeurd": [{"woord": "mpox", "soort": "woord"}],
                  "/rest/v1/naam_is_spelfout": [{"woord": "Hairi"}]}
    verzoeken_gezien = []

    class NepSupabase(BaseHTTPRequestHandler):
        def do_GET(self):
            pad = self.path.split("?")[0]
            verzoeken_gezien.append(self.path)
            self.send_response(200 if pad in uitgereikt else 404)
            self.end_headers()
            if pad in uitgereikt:
                self.wfile.write(json.dumps(uitgereikt[pad]).encode())

        def log_message(self, *args):
            pass

    nep = HTTPServer(("127.0.0.1", 0), NepSupabase)
    threading.Thread(target=nep.serve_forever, daemon=True).start()
    try:
        lijsten = tijdelijk / "lijsten"
        lijsten.mkdir()
        run = subprocess.run([sys.executable, str(WORTEL / "scripts" / "haal_goedgekeurd.py"), str(lijsten / "goedgekeurd.json")],
                             capture_output=True, text=True,
                             env={**os.environ, "SUPABASE_URL": f"http://127.0.0.1:{nep.server_port}",
                                  "SUPABASE_SERVICE_ROLE_KEY": "sleutel"})
        controle("beide lijsten worden opgehaald en bewaard", run.returncode == 0 and
                 json.loads((lijsten / "goedgekeurd.json").read_text()) == uitgereikt["/rest/v1/goedgekeurd"] and
                 json.loads((lijsten / "naam_is_spelfout.json").read_text()) == [{"woord": "Hairi"}], run.stderr[-200:])
        controle("alleen de actieve rijen worden gevraagd",
                 any("ingetrokken_op=is.null" in v for v in verzoeken_gezien) and
                 any("teruggezet_op=is.null" in v for v in verzoeken_gezien), str(verzoeken_gezien))
        del uitgereikt["/rest/v1/naam_is_spelfout"]      # de tweede tabel antwoordt met een fout
        (lijsten / "goedgekeurd.json").unlink()
        run = subprocess.run([sys.executable, str(WORTEL / "scripts" / "haal_goedgekeurd.py"), str(lijsten / "goedgekeurd.json")],
                             capture_output=True, text=True,
                             env={**os.environ, "SUPABASE_URL": f"http://127.0.0.1:{nep.server_port}",
                                  "SUPABASE_SERVICE_ROLE_KEY": "sleutel"})
        controle("mislukt de tweede lijst, dan stopt de run en blijft er niets half achter",
                 run.returncode != 0 and not (lijsten / "goedgekeurd.json").exists())
    finally:
        nep.shutdown()

    print("\nGoedgekeurde woorden ophalen")
    # Dit is de enige lijst. Lukt het ophalen niet, dan moet de run stoppen en geen
    # leeg bestand achterlaten waarmee de crawl stilletjes doorgaat.
    uit = tijdelijk / "gk-ophalen.json"
    omgeving = {**os.environ, "SUPABASE_URL": "http://127.0.0.1:1",
                "SUPABASE_SERVICE_ROLE_KEY": "sleutel"}
    mislukt_run = subprocess.run([sys.executable, str(WORTEL / "scripts" / "haal_goedgekeurd.py"),
                                  str(uit)], capture_output=True, env=omgeving)
    controle("onbereikbaar Supabase laat de run stoppen", mislukt_run.returncode != 0)
    controle("en laat geen leeg bestand achter", not uit.exists())
    zonder = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
    mislukt_run = subprocess.run([sys.executable, str(WORTEL / "scripts" / "haal_goedgekeurd.py"),
                                  str(uit)], capture_output=True, env=zonder)
    controle("een ontbrekende sleutel laat de run ook stoppen", mislukt_run.returncode != 0)

    print("\nGoedgekeurde woorden met een apostrof")
    uitz = {"natuurrisico's", "radiotaxi"}
    zin = "Let op natuurrisico\u2019s en radiotaxi\u2019s in het land."
    over = [b["woord"] for b in zoek_fouten(zin, uitz)]
    controle("gekrulde apostrof telt als rechte", "natuurrisico's" not in over, f"over: {over}")
    controle("goedgekeurd woord dekt het meervoud", "radiotaxi's" not in over, f"over: {over}")

    print("\nHuisstijl met een plus")
    huis = {"lhbtiq+", "vriendelijke"}
    controle("lhbtiq+ wordt goedgekeurd", "lhbtiq+" not in woorden_in_met("Een lhbtiq+ persoon.", huis))
    controle("lhbtiq zonder plus wordt gemeld", "lhbtiq" in woorden_in_met("Een lhbtiq persoon.", huis))
    controle("samenstelling over beide lijsten",
             "lhbtiq+-vriendelijke" not in woorden_in_met("Een lhbtiq+-vriendelijke stad.", huis))

    print("\nSpelfout of naam")
    # Deze indeling haalt ruim 90% van de meldingen uit beeld, dus hij moet
    # kloppen op precies de gevallen waarop het besluit is genomen.
    controle("hoofdletter middenin een zin is een naam",
             soort_van("Cochabamba", "Zoals de steden La Paz en Cochabamba.") == "naam")
    controle("hoofdletter aan het zinsbegin blijft een spelfout",
             soort_van("Registeer", "Registeer u bij de ambassade.") == "spelfout")
    controle("kleine letter middenin blijft een spelfout",
             soort_van("nieet", "Reis nieet naar dit gebied.") == "spelfout")
    controle("aanhalingsteken voor het zinsbegin telt niet mee",
             soort_van("Registeer", "\u2018Registeer u,\u2019 zegt de ambassade.") == "spelfout")
    controle("vergeten spatie gaat voor de hoofdletterregel",
             soort_van("III.Let", "De koers van segmento III.Let op dat u wisselt.") == "spelfout")
    controle("vergeten spatie na een klein woord",
             soort_van("demonstraties.Volg", "Vermijd demonstraties.Volg het nieuws.") == "spelfout")
    controle("webadres is geen vergeten spatie",
             soort_van("Windy.com", "Bekijk de windkaart op Windy.com vandaag.") == "naam")
    controle("afkorting met punten is geen vergeten spatie",
             soort_van("U.S", "Lees dit op de website van het U.S Department.") == "naam")
    controle("de soort staat in elke bevinding",
             all(b["soort"] in ("spelfout", "naam")
                 for b in zoek_fouten("Reis nieet naar Cochabamba.", set())))

    print("\nSjabloonresten (rommel uit het CMS)")
    # "undefined" stond zichtbaar boven aan reisadvies/estland. Deze meldingen
    # mogen nooit wegvallen: een bezoeker ziet ze wel.
    schoon = {"reist", "u", "naar", "voor", "het", "reisadvies", "is", "geel",
              "de", "grens", "bij", "aankomst", "en", "aantal", "nul",
              "nulmeting", "object", "gedaan", "zijn", "terrorisme", "er", "niet"}
    def resten(zin):
        return [b["woord"] for b in zoek_fouten(zin, schoon)]
    controle("undefined wordt gemeld",
             "undefined" in resten("undefined Terrorisme is er niet."))
    controle("[object Object] wordt heel gemeld, niet stukgeknipt",
             resten("Reist u naar [object Object] voor het reisadvies.") == ["[object Object]"])
    controle("onvervangen sjabloonveld met accolades",
             "{{land}}" in resten("Het reisadvies voor {{land}} is geel."))
    controle("onvervangen sjabloonveld met dollarteken",
             "${land}" in resten("Het reisadvies voor ${land} is geel."))
    controle("dubbel ontsnapte HTML",
             resten("De grens bij&nbsp;aankomst.") == ["&nbsp;"])
    controle("de rest wordt niet dubbel gemeld",
             resten("De grens bij&nbsp;aankomst.").count("&nbsp;") == 1)
    controle("de zin blijft ongewijzigd als context",
             all(b["context"] == "Het reisadvies voor {{land}} is geel."
                 for b in zoek_fouten("Het reisadvies voor {{land}} is geel.", schoon)))
    controle("gewoon Nederlands blijft met rust",
             resten("De nul en de nulmeting zijn gedaan.") == [])
    controle("een sjabloonrest telt als spelfout, niet als naam",
             all(b["soort"] == "spelfout"
                 for b in zoek_fouten("Reist u naar [object Object] voor het reisadvies.", schoon)))

    print("\nPatronen uit robots.txt")
    for patroon, pad, verwacht in [
        ("/api/*", "/api/iets", True), ("/api/*", "/apart", False),
        ("/zoeken?*", "/zoeken?q=a", True), ("/zoeken?*", "/zoekenlijst", False),
        ("/x$", "/x", True), ("/x$", "/xy", False),
    ]:
        controle(f"{patroon} tegen {pad}", bool(naar_patroon(patroon).match(pad)) == verwacht)

    print("\nTekst uit een pagina halen")
    controle("geen <main> geeft lege tekst", tekst_uit_main("<p>hoi</p>") == "")
    controle("script wordt overgeslagen",
             "verstopt" not in tekst_uit_main("<main><script>verstopt</script>tekst</main>"))
    controle("entiteiten worden vertaald",
             tekst_uit_main("<main>caf&eacute;</main>") == "café")

    print("\nWoordvormen")
    woordjes = {"radiotaxi", "consulaat", "generaal", "nood", "bus", "chauffeur"}
    controle("meervoud met apostrof", is_bekend("radiotaxi's", woordjes))
    controle("samenstelling met koppelteken", is_bekend("consulaat-generaal", woordjes))
    controle("onzin blijft onbekend", not is_bekend("radiotaxy's", woordjes))

    print("\nWoorden uit een zin halen")
    def woorden_in(zin):
        return [b["woord"] for b in zoek_fouten(zin, set())]

    def woorden_in_met(zin, toegestaan):
        return [b["woord"] for b in zoek_fouten(zin, toegestaan)]
    controle("weglatingsstreepje", "Nood" in woorden_in("Nood- of crisissituatie."))
    controle("schuine streep splitst",
             woorden_in("Laat familie/vrienden weten.")[1:3] == ["familie", "vrienden"])
    controle("haakje middenin splitst", "chauffeur" in woorden_in("Wijs de (bus)chauffeur erop."))
    controle("koppelteken blijft heel", "e-mail" in woorden_in("Stuur een e-mail."))
    controle("e-mailadres wordt overgeslagen",
             not any("@" in w for w in woorden_in("Mail naar iemand@voorbeeld.nl vandaag.")))
    controle("onzichtbare tekens weg", "adres" in woorden_in("Het a\u200bdres."))

    if offline:
        print("\n(robots.txt tegen de echte site overgeslagen: --offline)")
    else:
        print("\nrobots.txt van de echte site")
        mag = maak_robots_controle()
        controle("gewone pagina mag", mag(SITE + "/reisadvies/albanie"))
        controle("/zoeken? geblokkeerd", not mag(SITE + "/zoeken?q=paspoort"))
        controle("/api/ geblokkeerd", not mag(SITE + "/api/iets"))

    mislukt = uitkomsten.count(False)
    print(f"\n{len(uitkomsten) - mislukt} van {len(uitkomsten)} controles goed.")
    return 1 if mislukt else 0


if __name__ == "__main__":
    sys.exit(main())
