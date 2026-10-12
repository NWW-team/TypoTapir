---
name: SpellingSpeurneus
last_updated: 2026-10-05
---

# SpellingSpeurneus — Strategie

## Doelprobleem

Een webredacteur bij een site met duizenden pagina's en dagelijks wijzigende content heeft nu geen methode om spelfouten te vinden — handmatig controleren is op die schaal niet haalbaar.

## Onze aanpak

De redacteur start zelf een crawl wanneer hij dat nodig acht, in plaats van dat het systeem continu op de achtergrond alles scant — continu scannen van duizenden dagelijks wijzigende pagina's is onnodig.

## Voor wie

**Primair:** Webredacteur — hij huurt SpellingSpeurneus in om de kwaliteit van de websitecontent te bewaken door spelfouten op te sporen, omdat spelfouten de geloofwaardigheid van de website aantasten.

## Sporen

### Content crawlen

De site doorlopen op verzoek van de redacteur om paginacontent op te halen.

_Waarom het de aanpak dient:_ maakt het crawlen-op-verzoek mogelijk in plaats van continu scannen.

### Vergelijken met woordenlijst

Content toetsen aan een lijst met goedgekeurde spelling om afwijkingen te vinden.

_Waarom het de aanpak dient:_ levert de daadwerkelijke spelfouten op die de redacteur zoekt.

### Overzicht tonen

Resultaten presenteren aan de redacteur, met filtering op URL en op woord, en met een Excel-download van de spelfouten en van de namen.

_Waarom het de aanpak dient:_ maakt de bevindingen bruikbaar voor de redacteur om gericht te controleren, en om ze met collega's te delen.

### Crawl starten, volgen en stoppen

De redacteur kiest in het scherm een deel van de site (reisadviezen, visum voor Nederland, visum voor de Caribische Koninkrijksdelen, ambassades en consulaten), start de crawl, ziet de voortgang en kan hem stoppen. Er mag één crawl per dag.

_Waarom het de aanpak dient:_ de redacteur beslist zelf wanneer er gecrawld wordt, zonder dat hij een GitHub-account of technische kennis nodig heeft. De limiet beschermt de site tegen te veel verkeer.

### Vals alarm wegwerken

De redacteur keurt een woord of naam goed met één klik. Het verdwijnt uit de lijst en de volgende crawl slaat het over. Eén lijst, in de database, die de redactie zelf bijhoudt.

_Waarom het de aanpak dient:_ een woordenlijst kent niet alle goede woorden (vaktermen, huisstijl, namen). Zonder deze stap blijft de lijst vol vals alarm en kijkt niemand meer naar de echte fouten.

### Namen nakijken

Namen worden apart gezet en beoordeeld tegen een lijst met plaatsen (GeoNames): bekend, of lijkt op een bekende plaats. Een naam die fout blijkt, verplaatst de redacteur naar de spelfouten.

_Waarom het de aanpak dient:_ in de eerste crawl was ruim 90% van de meldingen een naam. Zonder scheiding verdrinken de echte fouten, maar weggooien kan niet, want een verkeerd gespelde plaatsnaam is ook een fout op de site.

### Toegang beperken tot de redactie

_Vervallen op 2 oktober 2026:_ er is geen inlog meer. De pagina is alleen via een
niet-aangekondigde link te vinden; de gegevens zijn leesbaar voor wie de publieke key
heeft. Zie besluit 6 in OVERDRACHT.md.
