// Start de Crawl-workflow in GitHub, hooguit één keer per dag. Vervangt de knop
// "Run workflow" op GitHub voor wie daar geen account voor heeft.
//
// Deze functie is voor iedereen aan te roepen (zie besluit 6 in OVERDRACHT.md). De
// bescherming is: de limiet van één crawl per dag, afgedwongen door een unieke index
// in de database, en een vaste lijst met bronnen en een bovengrens op het aantal
// pagina's. Het GitHub-token staat als secret `GITHUB_TOKEN` in Supabase en komt
// nooit in de browser. Het heeft alleen Actions: schrijven op deze repository nodig.
import { createClient } from "npm:@supabase/supabase-js@2";

const REPO = "NWW-team/SpellingSpeurneus";
const WORKFLOW = "crawl.yml";
const BRONNEN = ["reisadvies", "visum-nederland", "caribisch-visum", "ambassades"];
const MAX_PAGINAS = 5000;
const KOP = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const antwoord = (status: number, lichaam: unknown) =>
  new Response(JSON.stringify(lichaam), {
    status, headers: { ...KOP, "Content-Type": "application/json" },
  });

Deno.serve(async (verzoek) => {
  if (verzoek.method === "OPTIONS") return new Response(null, { status: 204, headers: KOP });
  if (verzoek.method !== "POST") return antwoord(405, { fout: "Alleen POST." });

  let invoer: { bron?: unknown };
  try { invoer = await verzoek.json(); } catch { return antwoord(400, { fout: "Geen geldige JSON." }); }

  const { bron } = invoer;
  if (typeof bron !== "string" || !BRONNEN.includes(bron)) return antwoord(400, { fout: "Onbekend deel van de site." });
  // Een crawl pakt altijd het hele deel. Het aantal staat vast op een grens boven het grootste
  // deel; een aantal in het verzoek (van een oude versie van het scherm) wordt genegeerd.
  const max_paginas = MAX_PAGINAS;

  const token = Deno.env.get("GITHUB_TOKEN");
  if (!token) return antwoord(500, { fout: "Het GitHub-token is niet ingesteld in Supabase." });

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  // Eerst de dag reserveren, dan pas GitHub aanroepen. Zo kunnen twee gelijktijdige
  // aanvragen er niet allebei doorheen: de unieke index laat er maar één toe.
  const { data: rij, error } = await db.from("crawl_aanvragen")
    .insert({ bron, max_paginas }).select("id").single();
  if (error) {
    if (error.code === "23505") {
      return antwoord(429, { fout: "Er is vandaag al een crawl gestart. Morgen kan er weer één." });
    }
    return antwoord(500, { fout: "Kan de aanvraag niet opslaan." });
  }

  const gh = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "SpellingSpeurneus",
    },
    // GitHub wil alle inputs als tekst. opentaal_ref blijft op de standaardwaarde. De workflow
    // kent geen maximumaantal pagina's meer (een crawl pakt het hele deel); een input die de
    // workflow niet kent wordt door GitHub geweigerd. aanvraag_id laat de crawler zijn
    // voortgang aan deze rij melden en maakt de crawl stopbaar.
    body: JSON.stringify({ ref: "main", inputs: { bron, aanvraag_id: String(rij.id) } }),
  });

  if (!gh.ok) {
    // Niet gestart, dus de dag niet laten verbranden.
    await db.from("crawl_aanvragen").delete().eq("id", rij.id);
    return antwoord(502, { fout: `GitHub weigerde de aanvraag (${gh.status}).` });
  }
  return antwoord(200, { ok: true });
});
