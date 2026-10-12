# SpellingSpeurneus

Zoekt spelfouten op [nederlandwereldwijd.nl](https://www.nederlandwereldwijd.nl),
wanneer de webredacteur daarom vraagt. Zie [STRATEGY.md](STRATEGY.md) voor het waarom
en [OVERDRACHT.md](OVERDRACHT.md) voor de stand van zaken, de openstaande besluiten
en wat je moet weten als je hieraan verder werkt.

**Resultaten bekijken:** https://nww-team.github.io/SpellingSpeurneus/ — zonder inlog. Zie [Toegang](#toegang).

## Hoe het werkt

1. Je drukt in het scherm op **Crawl starten** en kiest een deel van de site. Een crawl
   pakt altijd het hele deel; er is geen maximumaantal pagina's om in te stellen, ook niet bij
   de knop **Run workflow** van [de Crawl-workflow](../../actions/workflows/crawl.yml) in
   GitHub, waar alleen het deel te kiezen is. Er mag één crawl per dag via het scherm. Een
   lopende crawl is te volgen aan de voortgangsbalk en met **Crawl stoppen** te stoppen.
2. Een GitHub-runner leest de sitemaps, haalt de pagina's van het gekozen deel op en pakt de
   tekst uit het `<main>`-element. Menu's en voetteksten blijven buiten beeld.
3. Elk woord wordt getoetst aan de OpenTaal-woordenlijst en aan de goedgekeurde woorden
   en namen in Supabase (tabel `goedgekeurd`, zie [Vals alarm wegwerken](#vals-alarm-wegwerken)).
4. Wat overblijft wordt in tweeën gedeeld: **spelfouten** en **namen**. Zie hieronder.
5. Het resultaat gaat naar Supabase en verschijnt op de pagina hierboven.

Er draait niets automatisch op de achtergrond. Een crawl gebeurt alleen als iemand erom vraagt.

**Een crawl stoppen.** Zolang er gecrawld of voorbereid wordt, staat onder de voortgangsbalk de knop
**Crawl stoppen**. Die roept de Edge Function
[`crawl-stoppen`](supabase/functions/crawl-stoppen/stoppen.ts) aan, die de run in GitHub annuleert
en de aanvraag op `gestopt` zet. Er wordt dan niets gepubliceerd: wat tot dan toe is gevonden
gaat verloren, want de crawl publiceert pas aan het eind. Tijdens het opslaan van het resultaat
kan stoppen niet meer, anders blijft er een half resultaat achter. Een gestopte of mislukte
crawl telt niet mee voor de limiet van één per dag. De functie vindt de run via de link die de
workflow bij de aanvraag opslaat; ontbreekt die nog (de eerste seconden), dan zoekt ze de ene
lopende run die na de aanvraag is gestart, en bij twijfel stopt ze niets.

De knop roept de Edge Function [`crawl-starten`](supabase/functions/crawl-starten/index.ts)
aan, die de workflow in GitHub start. Het GitHub-token staat als secret `GITHUB_TOKEN` in
Supabase en heeft alleen *Actions: read and write* op deze repository. De limiet van één per
dag zit in de database (tabel `crawl_aanvragen`, unieke index op de datum in Nederlandse
tijd), dus twee gelijktijdige aanvragen komen er niet allebei door. Mislukt het starten bij
GitHub, dan wordt de aanvraag weer verwijderd en blijft de dag beschikbaar.

## Delen van de site

Je kiest een deel van de site; alles onder dat pad hoort erbij.

| Deel | Pad | Pagina's (±) |
|---|---|---|
| Reisadviezen | `/reisadvies` | 236 |
| Visum voor Nederland | `/visum-nederland` | 1.015 |
| Visum voor Caribische Koninkrijksdelen | `/caribisch-visum` | 452 |
| Ambassades en consulaten | `/contact/ambassades-consulaten-generaal` | 219 |

De pagina's staan verspreid over de sitemaps van de site (de visumpagina's zitten in de
grote `paginas`-sitemap), dus de crawler leest ze allemaal en houdt over wat onder het pad
valt. Een deel toevoegen is één regel in `DELEN` in `scripts/crawl.py`, plus dezelfde naam in
de lijst in de workflow, in de Edge Function `crawl-starten`, in de controle op
`crawl_aanvragen.bron` en in `DEEL_INFO` in `docs/index.html`. De overige pagina's van de
site (alles buiten deze vier paden) zijn geen keuze.

## Spelfouten en namen

De woordenlijst kent geen plaats- en organisatienamen. Op reisadviespagina's staan die
overal, dus zonder scheiding verdrinken de echte fouten erin: de crawl over alle 226
reisadviezen gaf 3.376 meldingen, waarvan er 2.949 een naam waren.

Daarom deelt de app elke melding in. **Een woord met een hoofdletter middenin een zin is
een naam**; aan het zinsbegin zegt een hoofdletter niets, dus daar toetsen we gewoon door.
Een vergeten spatie gaat voor: `III.Let op dat u` begint met een hoofdletter maar is een
echte fout. Dezelfde crawl levert zo 427 spelfouten op en 1.398 namen op een tweede
tabblad: 87% van de meldingen verdwijnt uit beeld zonder verloren te gaan.

Namen worden dus **niet weggegooid**. Ze staan er één keer per naam, met een voorbeeldzin
en een link naar het reisadvies waar die zin staat — en als de naam op meer pagina's
voorkomt, staat erbij op hoeveel. Zo blijft een verkeerd gespelde plaatsnaam op te zoeken. De indeling
staat per bevinding in de kolom `soort`, dus wie de regel anders wil (hij staat in
`soort_van` in `scripts/crawl.py`) kan het scherm omgooien zonder opnieuw te crawlen.

### Plaatsnamen nakijken

De woordenlijst kent geen namen, dus `Cochabamba` en een verkeerd gespelde variant krijgen
dezelfde melding. Daarom krijgt elke naam een oordeel op basis van
[GeoNames](https://www.geonames.org) (plaatsen vanaf 1000 inwoners, regio's en landen):

| Oordeel | Betekenis |
|---|---|
| **bekende plaatsnaam** | Staat in GeoNames, ook met andere accenten (`Cordoba` = `Córdoba`). Geen aandacht nodig |
| **lijkt op …** | Staat er niet in, maar lijkt op één of twee letters na op een bekende plaats. Dit zijn de namen om eerst na te kijken; de suggestie staat erbij |
| *(niets)* | Staat er niet in en lijkt op niets: een organisatie, een persoon of een woord uit een andere taal. De lijst zegt hier niets over |

Boven de lijst staat een keuzelijst om alleen de namen van één groep te tonen. **Lijkt op** is
een hint, geen oordeel: het kan ook een organisatie zijn die toevallig op een plaats lijkt.
Is een naam goed, klik dan op **Goedkeuren**, dan komt hij er niet meer in terug.

### Een naam die verkeerd gespeld is

Zie je bij Namen een naam die fout is (`Hairi`, `Guyaquil`), klik dan op **Is een spelfout**. De
naam verdwijnt bij Namen en staat bij **Spelfouten**, met de aanduiding *verplaatst vanuit Namen* en,
als er een suggestie was, *lijkt op …*. Daar staat ook **Terug naar Namen** voor als je je vergist.
Het blijft gelden bij de volgende crawl: de crawler meldt zo'n woord dan direct als spelfout. De
verplaatste namen staan in de tabel `naam_is_spelfout`, apart van `goedgekeurd`: een foute naam mag
nooit per ongeluk als goed tellen.

Wat dit niet kan: een naam beoordelen die wél in GeoNames staat maar op die pagina niet de
plaats bedoelt, een verkeerde plaats die toevallig als andere plaats bestaat, of een naam die
meer dan twee letters afwijkt. Hoe het matcht staat in
[`scripts/plaatsnamen.py`](scripts/plaatsnamen.py). De workflow haalt de bestanden per run op;
lukt dat niet, dan krijgen namen geen oordeel en gaat de crawl gewoon door.

## Downloaden als Excel

Boven de lijst bij **Spelfouten** staat een knop **Download als Excel**. Het bestand
bevat wat nu in het tabblad staat: met de filters die je hebt gezet (URL en woord), en zonder wat
is goedgekeurd. Zonder filters is dat de hele lijst. De knop zegt hoeveel
rijen erin komen; staat er een filter aan, dan eindigt de bestandsnaam op `-gefilterd`, bijvoorbeeld
`spelfouten-visum-nederland-2026-10-02.xlsx`.

De kolommen zijn Pagina (de URL), Zin, Woord, Suggestie en Opmerking. Suggestie en Opmerking
blijven leeg: die vult de redacteur zelf in. In de Zin staat de spelfout vet. Sjabloonresten staan bovenaan. Bij **Namen** is geen
download: die lijst is bedoeld om na te lopen in het scherm.

Het bestand wordt in de browser gemaakt, zonder dat er iets naar een server gaat. Het heeft een vette
kopregel, een bevroren kopregel en filterknoppen. Alles is tekst, dus een woord dat met `=` of `+`
begint blijft tekst en wordt nooit een formule. De schrijver staat in
[`docs/xlsx.js`](docs/xlsx.js), zonder externe bibliotheek.

## Vals alarm wegwerken

Meldt de app een woord of naam die gewoon goed is? Klik op **Goedkeuren**. Het verdwijnt uit
de lijst en komt op het tabblad **Goedgekeurd** te staan; de volgende crawl slaat het over.
Een vergissing maak je daar ongedaan met **Intrekken**. Goedkeuringen staan in de Supabase-tabel
`goedgekeurd` en worden nooit verwijderd, alleen met een datum ingetrokken.

Goedkeuren en intrekken gaan via de Edge Function
[`supabase/functions/goedkeuren`](supabase/functions/goedkeuren/index.ts) en zijn begrensd tot
300 wijzigingen per uur. Zie [Toegang](#toegang): omdat er geen inlog is, kan iedereen met de
link dit doen.

**Er is maar één lijst met goedgekeurde woorden: de tabel `goedgekeurd`.** Het tabblad
Goedgekeurd in het scherm toont hem helemaal, alfabetisch en doorzoekbaar. De vroegere
`data/uitzonderingen.txt` is op 2 oktober 2026 in die tabel ingeladen en uit de repository
gehaald; zijn geschiedenis staat in git. De workflow haalt de lijst vlak voor de crawl op en
**stopt als dat niet lukt**: een crawl zonder die lijst meldt honderden goede woorden als fout.

Eén ding om te weten bij het lezen van de cijfers: die lijst wordt bijgewerkt op basis van
de pagina's die al gecrawld zijn. Op **nieuwe** pagina's ligt het aantal valse meldingen
daarom hoger. Gemeten: 0,84 per pagina op de al opgeschoonde eerste 50, tegen 2,19 op de
176 pagina's die daarna voor het eerst langskwamen. Reken met het hoogste getal.

## Zelf draaien

Geen installatie nodig; alleen Python 3.

```bash
python3 scripts/crawl.py --bron demo --max-paginas 5     # fictieve pagina's, zonder netwerk
python3 scripts/crawl.py --bron reisadvies --max-paginas 10   # ook: visum-nederland, caribisch-visum, ambassades
python3 -m http.server --directory docs 8000             # scherm bekijken op localhost:8000
python3 scripts/test.py                                  # 131 controles; --offline slaat het netwerk over
```

Het scherm heeft Supabase nodig om iets te tonen; lokaal zie je zonder internet niets. Het resultaat van een lokale crawl in Supabase zetten kan met:

```bash
export SUPABASE_URL=https://xxxxxxxx.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=...        # uit het dashboard, niet in een bestand
python3 scripts/crawl.py --bron demo --max-paginas 5 --uit resultaten.json
python3 scripts/publiceer.py --in resultaten.json
```

De workflow haalt per run de OpenTaal-lijst op (ruim 413.000 woorden) en vergelijkt de
sha256 met [`data/opentaal.sha256`](data/opentaal.sha256). Wijkt die af, dan waarschuwt de
run: je toetst dan aan een andere lijst dan de vorige keer.

Zonder `data/woordenlijst.txt` valt het script terug op `data/woordenlijst-demo.txt`. Dat is
een testlijst van ruim honderd woorden, alleen bedoeld voor `demo/`. De echte lijst haalt de
workflow per run op bij OpenTaal.

## Toegang

**Er is geen inlog meer.** De resultaten staan in Supabase en zijn leesbaar voor iedereen
die de publishable key heeft. Die staat in `docs/index.html`, in een publieke repository.
De "geheime link" naar de pagina is dus **geen toegangscontrole**: wie de repository leest,
kan de bevindingen ophalen. Dat is een bewuste keuze van de redactie (besluit 3 in
[OVERDRACHT.md](OVERDRACHT.md) is teruggedraaid). Schrijven kan de browser nog niet: alleen
de crawl-workflow, met de service-role key.

De migratie die dit instelt staat in
[`supabase/migrations/`](supabase/migrations/20261002000000_open_lezen.sql).

### Sleutels

| Wat | Waar | Waarom |
|---|---|---|
| Project-URL en **publishable key** | in `docs/index.html` en in de workflow, publiek | Daarvoor bedoeld. Verleent alleen wat de policies toestaan |
| **Service-role key** | alleen als GitHub Actions secret `SUPABASE_SERVICE_ROLE_KEY` | Zet RLS buiten werking. Nooit in de frontend, de repository of een prompt |
| Databasewachtwoord | nergens | Niet nodig |

Dat is dus **één** secret om te beheren. De project-URL staat gewoon in de
workflow, want die is niet geheim. De workflow heeft verder geen schrijfrecht op
de repository meer nodig.

## Fatsoenlijk crawlen

`robots.txt` van de site staat crawlen toe, behalve `/zoeken?*` en `/api/*`; die paden slaan
we over en dat is terug te zien in het logboek van elke run. Verder: een herkenbare
User-Agent met een link naar deze repository, een halve seconde tussen twee pagina's, en
altijd een harde bovengrens op het aantal pagina's.

## Wat hier staat

| Pad | Wat het is |
|---|---|
| `scripts/crawl.py` | De crawler en de spellingtoets. Alleen de standaardbibliotheek van Python |
| `scripts/test.py` | Controles: vindt de app de ingebouwde fouten, en volgt hij robots.txt |
| `docs/index.html` | Het scherm. Eén bestand, geen buildstap |
| `scripts/publiceer.py` | Zet het resultaat in Supabase, achter de toegangscontrole |
| `supabase/` | Migraties (in de SQL Editor te plakken) en de Edge Function `goedkeuren` |
| `docs/icoon-groot.png` | Dezelfde hond in 256 × 256 pixels, voor de kopbalk (88 pixels hoog, dus scherp op schermen met hoge resolutie) |
| `docs/icoon.png` | Het icoon naast de titel en in het browsertabblad (favicon): de hond met de neus omhoog, 128 × 128 pixels, met transparante hoeken |
| `docs/xlsx.js` | Maakt de Excel-downloads in de browser, zonder bibliotheek |
| `supabase/functions/naam-verplaatsen/` | Edge Function die een naam naar de spelfouten verplaatst of terugzet (de controle op het verzoek staat los, in `verplaatsen.ts`) |
| `scripts/plaatsnamen.py` | Beoordeelt namen tegen GeoNames: bekend, lijkt op een bekende plaats, of geen oordeel |
| `scripts/haal_goedgekeurd.py` | Haalt de in het scherm goedgekeurde woorden op, vlak voor de crawl |
| `data/opentaal.sha256` | De versie van de woordenlijst waarop wij ons baseren |
| `demo/` | Vijf fictieve pagina's met drie ingebouwde fouten, om op te testen |
| `OVERDRACHT.md` | Stand van zaken, openstaande besluiten, beperkingen en beheer |
| `.github/workflows/crawl.yml` | De knop die een crawl start |

## Vormgeving

Het scherm benadert de Rijkshuisstijl in de **kleuren**: donkerblauw `#154273` voor de
kopbalk en de links, hemelblauw `#007BC7` als accent, lichtblauw `#8FCAE7` op donkere
vlakken en een geel markeerveld. Elke tekstkleur is tegen zijn achtergrond op WCAG
AA-contrast getoetst, in de lichte én de donkere stand.

Het is met opzet een benadering en geen kopie. Er zit **geen logo, woordmerk of het
Rijksoverheid-lettertype** in: dit is een hulpmiddel voor de redactie en moet niet voor
een officiële pagina van de Rijksoverheid worden aangezien — zeker niet zolang de
resultaten publiek staan (zie besluit 3 in [OVERDRACHT.md](OVERDRACHT.md)).

De echte tokens staan in
[nl-design-system/rijkshuisstijl-community](https://github.com/nl-design-system/rijkshuisstijl-community).
Die zijn hier niet uit overgenomen: dat pakket komt via npm en dit scherm is bewust één
bestand zonder buildstap. Wil je het exact maken, neem dan de tokenwaarden over in de
CSS-variabelen bovenaan `docs/index.html`; alles hangt aan die variabelen.

## Gegevens

Deze app leest alleen openbare webpagina's en een openbare woordenlijst. Er gaat geen
interne informatie doorheen en de bevindingen bevatten alleen citaten uit pagina's die
toch al openbaar zijn.

Toch staan de resultaten niet meer publiek: ze zijn een werklijst van de redactie en
horen bij de redactie. Zie [Toegang](#toegang) voor wat dat wel en niet afschermt.

Er zijn nu wél sleutels in het spel. Persoonsgegevens: Supabase Auth bewaart per
testaccount een e-mailadres en een wachtwoordhash. Deze app slaat zelf geen wachtwoorden
op en vergelijkt er geen.

## Bronvermelding

Plaatsnamen worden beoordeeld met gegevens van [GeoNames](https://www.geonames.org), licentie
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

De spelling wordt getoetst aan de
[OpenTaal-woordenlijst](https://github.com/OpenTaal/opentaal-wordlist) van stichting
OpenTaal, die het Keurmerk Spelling van de Nederlandse Taalunie draagt. Licentie: Revised
BSD en/of CC BY 3.0.
