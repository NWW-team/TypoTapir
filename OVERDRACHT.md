# Overdracht

Wat een volgende sessie of collega moet weten om hier verder te kunnen. Voor hoe de app werkt voor wie hem
gebruikt: zie [README.md](README.md). Voor het waarom: [STRATEGY.md](STRATEGY.md).

Laatst bijgewerkt: **20 oktober 2026**.

TypoTapir is op 12 oktober gemaakt als **kopie van SpellingSpeurneus**, de Nederlandse app voor
nederlandwereldwijd.nl ([NWW-team/SpellingSpeurneus](https://github.com/NWW-team/SpellingSpeurneus)). De
opbouw en de werkwijze zijn gelijk; dit document beschrijft wat hier anders is en wat de stand is. Besluiten,
de uitleg van de toets en de risico's die voor beide apps gelden staan in de `OVERDRACHT.md` van het
Nederlandse origineel (besluit 1 tot en met 6, "Hoe de toets werkt", "Risico's en bekende beperkingen").
Wil je in een nieuwe chat met Claude doorwerken? Begin dan bij
[Verder werken in een nieuwe chat](#verder-werken-in-een-nieuwe-chat).

## In het kort

TypoTapir zoekt spelfouten op [netherlandsworldwide.nl](https://www.netherlandsworldwide.nl), de Engelstalige
site van Nederland Wereldwijd, in **Brits Engels met -ise**, wanneer de webredacteur daarom vraagt. Het scherm
staat op **https://nww-team.github.io/TypoTapir/**, zonder inlog. De redacteur drukt in de tab van het deel
op **Crawl starten**, volgt de voortgang, loopt de spelfouten en namen na en keurt goed wat goed is. Er draait
niets vanzelf.

**Stand op 20 oktober.** Alles is opgezet, gedeployd en getest met één echte crawl, en de redactie is begonnen
met nakijken:

| | |
|---|---|
| Repository | `NWW-team/TypoTapir`, branch `main` (squash-merges via pull requests; de laatste is 13) |
| Supabase | project **TypoTapir**, `zasfgsgmbapnhfsnqsrp`, regio eu-west-1, URL `https://zasfgsgmbapnhfsnqsrp.supabase.co` |
| Scherm | GitHub Pages, branch `main`, map `/docs` |
| Delen van de site | drie tabs: `visa-the-netherlands` (1.015 pagina's), `caribbean-visa` (452) en `making-appointment` (219); alles onder het pad, zonder vertalingen. Alle drie zijn al een keer gecrawld. `passport-id-card` is teruggezet (zie "De delen van de site") |
| Woordenlijst | Debian-pakket `wbritish` 2020.12.07-2 (SCOWL), 103.494 woorden; sha256 vastgelegd in `data/woordenlijst.sha256` |
| Controles | 139, `python3 scripts/test.py --offline` |
| Crawls | 4: Visa for the Netherlands (12 oktober), Caribbean visa (13 oktober), Making an appointment (16 oktober) en Passport or ID card (19 oktober, teruggezet). Alleen de eerste is hieronder beschreven |
| Goedgekeurd | 84 actieve goedgekeurde woorden en namen (20 oktober; op 13 oktober waren het 77) en 3 namen als spelfout aangewezen; de redactie is begonnen |

**De eerste crawl (12 oktober, 15.08 uur Nederlandse tijd).** De run duurde 17 minuten (de crawl zelf 15,5)
en was volledig groen. Hij pakte 1.038 pagina's, **inclusief 360 vertalingen** (`.fr`, `.es`, `.de`), want die
filter bestond toen nog in een eerdere vorm. Resultaat: 25.205 bevindingen, waarvan 14.080 spelfouten en
11.125 namen. Daarvan stond 97% van de spelfouten (13.663) op 23 pagina's waarvan de URL op `/fr`, `/es` of
`/de` eindigt: Franse en Spaanse checklists. De filter is daarna uitgebreid (zie "Vertalingen"), en de 14.864
bevindingen van die 23 pagina's zijn **met de hand uit die ene crawl verwijderd** (dus `crawls.aantal_paginas`
zegt 1.038, terwijl er voor 23 pagina's geen bevindingen zijn). Wat in het scherm staat: **417 spelfouten en
9.924 namen**. Een volgende crawl pakt 1.015 pagina's en heeft de verwijderde rijen niet meer.

**Wat in die 417 zit.** Het is een eerste indruk, niet door de redactie nagelopen:
- **Amerikaanse spelling**: `center`, `travelers`, `legalized`, `organization`, `authorization`, `organizer`,
  `authorized`. Terechte meldingen bij Brits Engels met -ise. De site gebruikt kennelijk een mengeling van
  Amerikaans en Oxford-Engels (-ize). Dit is een **besluit voor de redactie** (zie Open punten).
- **Goede woorden die de lijst niet kent**, voor Goedkeuren: `payslips` (61 keer op 34 pagina's), `VFS`, `eVisa`,
  `biometric`, `barcode`, `biodata`, `businessperson`, `intergovernmental`, `non-biometric`, `d'Ivoire`
  (uit Côte d'Ivoire).
- **Echte fouten**: `reservationof` (vergeten spatie).
- **Woorden uit andere talen** in documentnamen: Turks (`dökümü`, `hizmet`), Arabisch (`namah`, `talak`),
  Italiaans (`verbale`). Waarschijnlijk namen van documenten die de site in de brontaal laat staan.

## Hoe het in elkaar zit

Precies als bij het origineel:

```
 Redacteur ── browser ── docs/index.html (GitHub Pages, statisch, supabase-js)
                              │ leest met de publieke key          │ schrijft nooit zelf
                              ▼                                    ▼
                       Supabase (Postgres, RLS)  ◄──── Edge Functions (service-role, met limieten)
                              ▲                          goedkeuren · naam-verplaatsen
                              │ schrijft                 crawl-starten ──► GitHub Actions
                              │                          crawl-stoppen ──► (annuleert de run)
                 GitHub Actions: .github/workflows/crawl.yml
                 installeert wbritish, haalt goedgekeurd + GeoNames, crawlt, publiceert
```

| Onderdeel | Waar | Wat |
|---|---|---|
| Scherm | `docs/index.html`, `docs/xlsx.js`, `docs/icoon*.png` | Eén bestand, geen buildstap. Tabs per deel (nu drie), crawlknop in de tab, Excel bij Spelfouten (Pagina, Zin met vet woord, Woord, Suggestie, Opmerking) |
| Crawler en toets | `scripts/crawl.py` | `SITE`, `DELEN`, `is_vertaling`, de toets zelf. Alleen standaardbibliotheek |
| Overige scripts | `scripts/plaatsnamen.py`, `haal_goedgekeurd.py`, `voortgang.py`, `publiceer.py` | Gelijk aan het origineel |
| Workflow | `.github/workflows/crawl.yml` | Invoer: `bron` (`demo` en de drie delen) en `aanvraag_id`. Er is geen `opentaal_ref` meer |
| Database | `supabase/migrations/` | Dertien migraties, **met de hand toegepast** (via de MCP, zie hieronder) |
| Edge Functions | `supabase/functions/` | Vier, `verify_jwt = false`, **met de hand gedeployd** (12 oktober, versie 1; `crawl-starten` is bij elk nieuw deel opnieuw gedeployd, nu versie 7 op 20 oktober) |

### Supabase

Tabellen, rechten en functies zijn die van het origineel (zie daar voor de beschrijving per tabel). Verschillen:
- Er is een **extra migratie** `20261001000000_crawls_en_bevindingen.sql`. In het origineel zijn `crawls` en
  `bevindingen` met de hand aangemaakt en stond dat in geen enkele migratie, waardoor de reeks op een leeg
  project niet werkt. De Nederlandse woordenlijst-import (`…050000_uitzonderingen_importeren.sql`) is hier
  weggelaten.
- `crawl_aanvragen.bron` mag de drie delen zijn, plus `passport-id-card` (zie "De delen van de site") (migratie `…070000`, daarna bij elk nieuw deel opgerekt: `20261013000000`, `20261016000000`, `20261019000000`).
- **Hoe het is toegepast**, voor wie de versies in de database vergelijkt: de migraties staan in
  `supabase_migrations` onder andere namen en tijdstippen (alle 12 oktober), en zijn deels samengevoegd of
  gesplitst. `open_lezen` is zonder het blok dat bestaande policies verwijdert toegepast (er waren er geen).
  Voortgang en stoppen (`20261002030000`, `20261005000000`) zijn als één geheel toegepast: de kolommen en de statuscontrole
  (met `gestopt`) via de MCP, en de **unieke index per dag** (alleen aanvragen die niet `mislukt` of `gestopt`
  zijn) in de SQL Editor, want `DROP INDEX` loopt via de MCP vast. Gecontroleerd op 12 en 13 oktober: de index
  heeft de juiste vorm.
- Gecontroleerd als `anon`: alleen `select` op alle vijf de tabellen, schrijven ingetrokken. De beveiligingscontrole
  van Supabase (`get_advisors`) meldt niets.

**Secrets.** GitHub (Actions): `SUPABASE_SERVICE_ROLE_KEY`. Supabase (Edge Functions): `GITHUB_TOKEN`, een
fine-grained token met alleen *Actions: read and write* op `NWW-team/TypoTapir`. Beide staan er en werken
(de crawl is erdoor gestart en afgerond). **Het token verloopt**; de vervaldatum is niet vastgelegd, zie Open punten.
De publieke Supabase-key (`sb_publishable_…`) staat bewust in `docs/index.html`.

### De delen van de site

`DELEN` in `crawl.py` heeft drie delen (Caribbean visa sinds 13 oktober, Making an appointment sinds 16 oktober;
migraties en Edge Function zijn toegepast). **De limiet van één crawl per dag geldt voor alle delen samen, bewust**
(besluit van de opdrachtgever, om te vaak crawlen te voorkomen): de unieke index in `crawl_aanvragen` staat alleen op
de datum, niet op het deel.

**Passport or ID card (`/passport-id-card`, 690 Engelse pagina's) is op 19 oktober toegevoegd en daarna weer
teruggezet**, omdat de tab nog niet goed genoeg werkt. Wat er nog van over is, en bewust is blijven staan:
- De crawl van 19 oktober staat nog in de database (3.421 bevindingen, `crawls.bron = 'passport-id-card'`). Het scherm
  toont hem niet, omdat het deel niet meer in `DEEL_INFO` staat.
- De 88 woorden die de redactie in de paspoort-tab had goedgekeurd (id 86 en 88 tot en met 174 in `goedgekeurd`, 19 oktober) zijn
  ingetrokken, niet verwijderd. `apostille` (id 87) is blijven staan: het komt ook in andere delen voor.
- De migratie `20261019000000_deel_passport_id_card.sql` is toegepast en laat `passport-id-card` nog toe in
  `crawl_aanvragen.bron`. Een strengere controle zou de bestaande crawl-aanvraag afwijzen.
- Uit de code zijn weg: de regel in `DELEN`, de workflow-optie, `BRONNEN` in `crawl-starten` (nu versie 7) en
  `DEEL_INFO`. Het deel kan dus niet meer worden gestart.

Wil je het deel terugzetten, draai dan de revert (pull request 13) terug.

| Deel | Pad | Pagina's |
|---|---|---|
| Visa for the Netherlands | `/visa-the-netherlands` | 1.015 (Engels, zonder vertalingen) |
| Caribbean visa | `/caribbean-visa` | 452 (Engels, zonder vertalingen; 581 met) |
| Making an appointment | `/making-appointment` | 219 (geen vertalingen) |

De sitemaps hebben ±5.850 URL's. Visa for the Netherlands heeft er 1.398, waarvan 383 vertalingen. Overige bovenste paden
(telling inclusief vertalingen), voor als er delen bij moeten komen:

| Pad | URL's | Pad | URL's |
|---|---|---|---|
| `/passport-id-card` | 878 | `/consular-fees` | 267 |
| `/declaration` | 868 | `/contact` | 222 |
| `/legalisation` | 310 | `/digid-abroad` | 136 |
| `/civic-integration-exam-abroad` | 271 | `/marry` (84), `/dutch-nationality` (57) | |

Een deel toevoegen kost (in deze volgorde): een regel in `DELEN`, de naam in `options` van de workflow, een migratie
voor de controle op `crawl_aanvragen.bron`, `BRONNEN` in `crawl-starten` én een regel in `DEEL_INFO` in
`docs/index.html`. Eerst de workflow mergen, dan de Edge Function deployen: GitHub weigert een invoer die de
workflow niet kent.

**Meet eerst of de sitemap het hele deel bevat.** De sitemaps staan niet altijd vol: onder
`/contact/embassies-consulates-general` stonden alleen de 218 landpagina's, terwijl er per land nog pagina's als
`/algeria/embassy-algiers` bestaan die alleen via links bereikbaar zijn. De crawler volgt geen links, dus die
pagina's waren niet gecrawld. Dat deel is daarom (op verzoek) **niet toegevoegd**. Wil je het alsnog, dan moet de
crawler links kunnen volgen binnen een deel (nog niet gebouwd). Voor de drie huidige delen is een steekproef van
25 tot 30 pagina's per deel gedaan zonder links buiten de sitemap te vinden; een volledige controle is niet gedaan.

### Vertalingen

De site zet vertalingen **naast** de Engelse pagina, op twee manieren: als achtervoegsel
(`/visa-the-netherlands/waiting-time-after-visa-application.fr`) en als laatste deel van het pad
(`/visa-the-netherlands/checklist-schengen-visa-seafarer/fr`). Het veld `lang` in de pagina zegt bij alle
`en`, dus alleen de URL verraadt ze. Zonder filter meldt een Britse woordenlijst elk Frans, Spaans en Duits
woord als fout (13.663 meldingen in de eerste crawl). `is_vertaling()` in `crawl.py` herkent een achtervoegsel van
twee letters met een punt, en `/fr`, `/es`, `/de` als laatste padsegment. Het tweede geval is bewust beperkt tot
die drie talen: een willekeurig segment van twee letters (`/us`) kan een gewone pagina zijn. Komt er een taal bij
(bijvoorbeeld `/nl`), voeg die dan toe aan `TALEN` in `crawl.py`; de tests staan in `scripts/test.py`
("Delen van de site"). De crawl meldt in het logboek hoeveel vertalingen hij overslaat.

Pagina's in het Engels bevatten wel een taalkeuze: "Language selection: English Change language: Deutsch Español
Français". Die woorden komen als namen in de lijst. Goedkeuren (één keer) of de tekst uit de crawl halen.

### De woordenlijst

De workflow doet `sudo apt-get install wbritish` en gebruikt `/usr/share/dict/british-english` als
`data/woordenlijst.txt`. Dat is SCOWL 2020.12.07, Brits met -ise, 103.494 regels (121.814 vormen na het toevoegen
van kleine letters). Gekozen omdat het een pakket is dat Ubuntu beheert, en dus geen URL die kan verdwijnen:
de oorspronkelijke SCOWL is sinds februari 2026 vervangen door een nieuw formaat. De run controleert het aantal
regels (minstens 50.000), print de sha256 en waarschuwt als *organise*, *colour*, *don't* of *London's* ontbreekt
of *color* erin staat. Bij de eerste crawl waren er geen waarschuwingen. Wijkt de sha256 af van
`data/woordenlijst.sha256`, dan waarschuwt de run en gaat hij door; klopt de nieuwe lijst, werk dan dat bestand bij.

Woorden met een apostrof ("don't", "London's", "countries'") worden goed behandeld zolang ze in de lijst staan
of op een bekend woord eindigen op `'s` (`is_bekend` in `crawl.py`). Samengestelde woorden met een
koppelteken worden per deel getoetst. Zie de tests onder "Engelse tekst".

De **demopagina's en de tests voor de toets zelf zijn nog Nederlands** (`demo/`, `data/woordenlijst-demo.txt`,
de voorbeeldzinnen in `scripts/test.py`). Dat testen de code, niet de taal, en het werkt; maak ze Engels als
je ze aanpast. De uitleg in het scherm en in de documenten is Nederlands.

## Zo werk je eraan

**Normaal verloop.** Branch maken vanaf `main`, aanpassen, `python3 scripts/test.py --offline`, pushen, PR,
mergen. Mergen naar `main` publiceert het scherm via GitHub Pages (een minuut of twee, daarna hard verversen).
In het dagelijks gebruik betekent "deploy" hier: de pull request mergen, en voor Supabase de migratie of de
Edge Function zelf toepassen. **Wat niet vanzelf gaat:**
- **Migraties** worden niet door een pipeline toegepast; plak ze in de SQL Editor of draai ze via de MCP. Controleer
  na een nieuwe tabel de policy én de grants, en toets als `anon`. **`DROP INDEX` en soms meerdere
  statements in één opdracht lopen via de MCP vast** (time-out na 60 s); doe zulke opdrachten in de SQL Editor,
  en controleer na een time-out eerst wat er is toegepast, want de opdracht kan half geslaagd zijn.
- **Edge Functions** worden niet door een pipeline gedeployd. Deploy via het dashboard of de MCP
  (`deploy_edge_function`), met **Verify JWT uit**, en neem de bestanden uit `supabase/functions/` over.
- **Cache.** `xlsx.js` en de iconen worden met een versienummer geladen (`xlsx.js?v=2`, `icoon.png?v=2`). Wijzig je
  `xlsx.js` of een icoon, **verhoog dan het versienummer** in `docs/index.html`, anders houden browsers (en de cache
  van GitHub Pages) een oude kopie vast. Zo ging het mis bij het origineel: een Excel met `[object Object]`.
- **Git in Claude Code op het web.** De ontwikkelbranch heet `claude/serene-allen-blqd14`. Na een squash-merge loopt die
  achter op `main`; zet hem voor een nieuwe wijziging opnieuw op vanaf `main`
  (`git fetch origin main && git checkout -B claude/serene-allen-blqd14 origin/main`) en push met
  `--force-with-lease`. Een stophook meldt anders onuitgepushte commits die al op `main` staan. De clone is ondiep en
  volgt alleen `main`: `git remote set-branches --add origin claude/serene-allen-blqd14`.

**Netwerk in Claude Code op het web.** De omgeving staat standaard dicht voor sites buiten een lijst. Voor deze app
is `www.netherlandsworldwide.nl` toegevoegd onder *Allowed domains* (de menu-instelling van de cloudomgeving,
Network access); daarmee kan Claude de sitemap, `robots.txt` en pagina's lezen. Niet bereikbaar zijn onder meer
github.com en de Pages-link zelf, `*.supabase.co` rechtstreeks, download.geonames.org, PyPI en het npm-register. De
GitHub- en Supabase-koppelingen (MCP) werken wel. De echte woordenlijst (`wbritish`) en GeoNames zijn dus
alleen in de workflow te gebruiken.

**Zo lees je het logboek van een crawl.** GitHub › Actions › de run › job `crawl`. Stap *Woordenlijst ophalen* toont
versie, regels, sha256 en waarschuwingen; stap *Crawlen en spelling toetsen* toont het aantal pagina's en de
vertalingen die zijn overgeslagen, en eindigt met het aantal bevindingen. Claude kan dit via de GitHub-koppeling
zelf lezen (`actions_list`, `get_job_logs`; het logboek is groot, dus lees het uit het opgeslagen bestand).
Twee dingen zijn geen fout: "LET OP: er zijn geen goedgekeurde woorden" zolang er nog niets goedgekeurd is, en
"Voortgang melden mislukte (Connection refused)" (dat is een test van de workflow die een onbereikbare server nabootst).

## Open punten

In volgorde van belang.

1. **De eerste resultaten nalopen**: de redactie is begonnen (77 woorden goedgekeurd op 13 oktober). Verder:
   terechte woorden goedkeuren (zie "Wat in die 417 zit"), de namenlijst doorlopen, en de echte fouten (zoals
   `reservationof`) naar de webredactie sturen.
2. **Besluit over Amerikaanse spelling.** De toets is Brits met -ise. De site gebruikt `center`, `travelers`
   (Amerikaans) en `organization`, `authorized` (Oxford, -ize). Past de redactie de site aan, dan zijn dit
   terechte meldingen. Wil de redactie -ize toestaan, dan is de woordenlijst anders nodig (het Britse -ize-bestand
   van SCOWL; `wbritish` heeft het niet) of moet het worden goedgekeurd. Keur **niet** goed wat de redactie wil laten
   aanpassen.
3. **Een tweede crawl**, ten vroegste de volgende dag (één per dag). Verwacht (voor Visa for the Netherlands): 1.015 pagina's, 383 vertalingen
   overgeslagen, "Woordenlijst is ongewijzigd ten opzichte van data/woordenlijst.sha256", en een kleinere
   spelfoutenlijst (goedgekeurde woorden zijn dan weg). Kijk of de namenlijst kleiner is en of er nog
   anderstalige pagina's tussen zitten.
4. **De namenlijst is groot (9.924).** De crawler behandelt elke hoofdletter midden in een zin als naam; op een
   visumsite zijn dat vooral landen en plaatsen. Mogelijke verbeteringen (nog niet gedaan): alles wat ook met een
   kleine letter in de woordenlijst staat niet als naam tellen (veel koppen en titels), de taalkeuze-woorden
   weglaten, en de plaatsnamencheck bijstellen. Bekijk eerst een tweede crawl.
5. **Het GitHub-token verloopt.** Zonder werken Crawl starten en Crawl stoppen niet meer ("GitHub weigerde …").
   De vervaldatum is niet genoteerd: kijk onder GitHub › Settings › Developer settings › Fine-grained tokens, zet
   een herinnering, maak dan een nieuw token (zelfde rechten, alleen deze repository) en vervang het
   Supabase-secret `GITHUB_TOKEN`.
6. **De sitebeheerder van netherlandsworldwide.nl inlichten.** We houden ons aan `robots.txt` (blokkeert alleen
   `/search?*` en `/api/*`), een halve seconde tussen pagina's en een herkenbare User-Agent
   (`TypoTapir/0.1 (+https://github.com/NWW-team/TypoTapir)`), maar het is netjes dat ze het van ons horen.
   Iedereen met de link kan één crawl per dag starten.
7. **Meer delen van de site** (zie de tabel hierboven), zodra de redactie dat wil.
8. **De taal van de interface.** De site die de app bekijkt is Engels; het scherm en de documentatie zijn
   Nederlands. Dat is nu zo gelaten. Wordt het scherm ook voor Engelstalige gebruikers bedoeld, dan moeten de
   teksten in `docs/index.html` vertaald worden.
9. **Opruimen** (geen haast): de README is deels nog Nederlands van herkomst; de demopagina's en testzinnen zijn
   Nederlands (zie boven).
10. **Een eigenaar bij de webredactie.** Zonder eigenaar verdwijnt zo'n prototype.

## Wat anders is dan bij SpellingSpeurneus

| | SpellingSpeurneus | TypoTapir |
|---|---|---|
| Site | nederlandwereldwijd.nl | netherlandsworldwide.nl |
| Taal | Nederlands (OpenTaal) | Brits Engels, -ise (SCOWL, `wbritish`) |
| Delen | vier | drie (`visa-the-netherlands`, `caribbean-visa`, `making-appointment`) |
| Vertalingen | niet van toepassing | `.fr`, `.es`, `.de`, `/fr`, `/es`, `/de` overgeslagen |
| Woordenlijst ophalen | download van OpenTaal, sha256 in `data/opentaal.sha256` | `apt-get install wbritish`, sha256 in `data/woordenlijst.sha256` |
| Supabase | `riwznqurcluudvyrkwxe` (eu-west-2) | `zasfgsgmbapnhfsnqsrp` (eu-west-1) |
| Goedgekeurde woorden | 924 actief | 84 actief (20 oktober) |
| Logo | hond | tapir |
| Migraties | tien, de basistabellen met de hand | dertien, met de basistabellen erbij |

**Een wijziging die in beide apps hoort, moet je twee keer doen**: het zijn kopieën, geen gedeelde code. Dat gold
voor de laatste wijzigingen aan de Excel, de tabs en de caching: die staan in beide.

## Verder werken in een nieuwe chat

Alles wat Claude nodig heeft staat in de repository en in dit document. Zet klaar:

1. **Toegang.** De GitHub-koppeling met `NWW-team/TypoTapir` (en `NWW-team/SpellingSpeurneus` als je de Nederlandse
   app ook raakt) en de Supabase-koppeling. Zet `www.netherlandsworldwide.nl` onder *Allowed domains* van de
   cloudomgeving als Claude de site moet kunnen bekijken.
2. **Een eerste bericht**, bijvoorbeeld:

   > Lees `OVERDRACHT.md` en `README.md` in NWW-team/TypoTapir (de Engelstalige variant van SpellingSpeurneus, het
   > Supabase-project heet TypoTapir). Daarna wil ik: …

3. **Werkafspraken** die tot nu toe golden en niet uit de code te halen zijn:
   - Antwoorden in het Nederlands, kort, met erbij wat is gecontroleerd en wat niet (een echte browser, Excel,
     de live site en de Pages-link zijn vaak niet te testen).
   - Een wijziging per verzoek, gecommit en gepusht op `claude/serene-allen-blqd14`. **Een pull request, mergen en
     deployen gebeuren pas na een uitdrukkelijk verzoek**; Claude vraagt dat na elke wijziging.
   - Schrijven in Supabase (migratie, Edge Function, gegevens verwijderen) alleen na akkoord, en liefst met de
     telling van wat er verandert vooraf. Zo is op 12 oktober gebeurd bij het verwijderen van de 14.864
     bevindingen van de vertalingen.
   - Sleutels en tokens nooit in de chat: de service-role key zet de redacteur zelf als GitHub-secret, het
     GitHub-token als Supabase-secret (de koppeling heeft daarvoor een opdracht die de waarde alleen in het
     dashboard laat invullen). De publishable key mag wel in de code.
   - Na het mergen van `docs/` een minuut of twee wachten en hard verversen.
4. **Checklist bij een wijziging aan het scherm:** `python3 scripts/test.py --offline`; het script in `docs/index.html`
   op syntaxis (`node --check`); het versienummer van `xlsx.js` of het icoon verhogen als je die wijzigt; README en dit
   document bijwerken als het gedrag, de kolommen of de cijfers veranderen.
5. **Checklist bij een nieuwe crawl:** lees het logboek (zie "Zo lees je het logboek van een crawl"), vergelijk met
   "Wat je dan verwacht" bij Open punten 3, en kijk bij een afwijking eerst naar `docs/` en `scripts/crawl.py`
   (vertalingen, taalkeuze, woordenlijst) voor je iets aan de database doet.
