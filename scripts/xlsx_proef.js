// Maakt een Excel-bestand met lastige gegevens, voor de controles in scripts/test.py.
//   node scripts/xlsx_proef.js <pad naar xlsx.js> <uitvoerbestand>
const { maakXlsx } = require(process.argv[2]);
const rijen = [
  ["nieet", 'Dat is nieet goed & <mooi> "zo".', "https://x.nl/a", 3],
  ["=1+1", '=HYPERLINK("http://evil","klik")', "+cmd", "@som"],
  ["Córdoba", "Zürich \u{1F30D} São", "", null],
  ["met\u0001stuur", "regel een\nregel twee", "x", 0],
  ["lang", "x".repeat(40000), "y", 1],
];
for (let i = 0; i < 300; i++) rijen.push(["w" + i, "zin " + i, "https://x.nl/" + i, i]);
// Opgemaakte tekst: een deel van de zin vet, met tekens die ontsnapt moeten worden.
rijen.push(["vet", ["Dat is ", { tekst: "nieet & <co", vet: true }, " goed."], "", null]);
require("fs").writeFileSync(process.argv[3], maakXlsx({
  werkblad: "Spel:fouten/Test[1]",
  kolommen: [
    { titel: "Woord", breedte: 24 }, { titel: "Zin", breedte: 80 },
    { titel: "Pagina", breedte: 50 }, { titel: "Aantal", breedte: 10 },
  ],
  rijen,
}));
