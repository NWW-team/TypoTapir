// Controles voor verplaatsen.ts. Draaien met:
//   node supabase/functions/naam-verplaatsen/verplaatsen.test.ts
// (Node 22.18 of nieuwer kan TypeScript zonder opties lezen.) scripts/test.py doet dit ook.
import process from "node:process";
import { MAX_PER_UUR, teVeel, valideer } from "./verplaatsen.ts";

let fout = 0;
const controle = (naam: string, gelukt: boolean, toelichting = "") => {
  if (!gelukt) fout++;
  console.log(`  ${gelukt ? "OK  " : "FOUT"} ${naam}${toelichting ? " — " + toelichting : ""}`);
};

console.log("Een naam naar de spelfouten verplaatsen");
const goed = valideer({ actie: "verplaatsen", woord: "Guyaquil" });
controle("een gewone naam is geldig", goed.ok && goed.actie === "verplaatsen" && goed.woord === "Guyaquil");
controle("terugzetten is een geldige actie", valideer({ actie: "terugzetten", woord: "Hairi" }).ok);
controle("witruimte rond het woord wordt weggehaald",
  (() => { const v = valideer({ actie: "verplaatsen", woord: "  Hairi " }); return v.ok && v.woord === "Hairi"; })());
controle("accenten en een apostrof mogen", valideer({ actie: "verplaatsen", woord: "l'Ouest-Haïtië" }).ok);
controle("een onbekende actie wordt geweigerd", !valideer({ actie: "verwijderen", woord: "x" }).ok);
controle("zonder actie wordt het geweigerd", !valideer({ woord: "x" }).ok);
controle("een leeg woord wordt geweigerd", !valideer({ actie: "verplaatsen", woord: "   " }).ok);
controle("geen woord wordt geweigerd", !valideer({ actie: "verplaatsen" }).ok);
controle("een getal als woord wordt geweigerd", !valideer({ actie: "verplaatsen", woord: 42 }).ok);
controle("een zin wordt geweigerd", !valideer({ actie: "verplaatsen", woord: "twee woorden" }).ok);
controle("een regeleinde midden in het woord wordt geweigerd", !valideer({ actie: "verplaatsen", woord: "een\nwoord" }).ok);
controle("een besturingsteken wordt geweigerd", !valideer({ actie: "verplaatsen", woord: "met\u0001stuur" }).ok);
controle("100 tekens mag, 101 niet",
  valideer({ actie: "verplaatsen", woord: "a".repeat(100) }).ok && !valideer({ actie: "verplaatsen", woord: "a".repeat(101) }).ok);
controle("de limiet telt verplaatsen en terugzetten samen",
  !teVeel(MAX_PER_UUR - 1, 0) && teVeel(MAX_PER_UUR - 1, 1) && teVeel(MAX_PER_UUR, 0) && teVeel(100, MAX_PER_UUR - 100));

console.log(fout ? `\n${fout} controle(s) mislukt.` : "\nAlles goed.");
if (fout) process.exit(1);
