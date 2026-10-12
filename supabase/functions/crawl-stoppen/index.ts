// Stopt de crawl die nu loopt, door de run in GitHub te annuleren. Het GitHub-token staat als
// secret `GITHUB_TOKEN` in Supabase (hetzelfde als bij crawl-starten); annuleren valt onder
// Actions: schrijven.
//
// Deze functie is voor iedereen aan te roepen (zie besluit 6 in OVERDRACHT.md). Ze doet alleen
// iets als er een crawl loopt, en stopt tijdens het opslaan van het resultaat niet meer.
import { createClient } from "npm:@supabase/supabase-js@2";
import { type Aanvraag, type GitHub, type Opslag, stopCrawl } from "./stoppen.ts";

const REPO = "NWW-team/SpellingSpeurneus";
const WORKFLOW = "crawl.yml";
const LOPEND = ["aangevraagd", "crawlen", "publiceren"];
const KOP = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, apikey, authorization",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const antwoord = (status: number, lichaam: unknown) =>
  new Response(JSON.stringify(lichaam), {
    status,
    headers: { ...KOP, "Content-Type": "application/json" },
  });

Deno.serve(async (verzoek) => {
  if (verzoek.method === "OPTIONS") return new Response(null, { status: 204, headers: KOP });
  if (verzoek.method !== "POST") return antwoord(405, { fout: "Alleen POST." });

  const token = Deno.env.get("GITHUB_TOKEN");
  if (!token) return antwoord(500, { fout: "Het GitHub-token is niet ingesteld in Supabase." });

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  const opslag: Opslag = {
    async actieveAanvraag(): Promise<Aanvraag | null> {
      const { data, error } = await db.from("crawl_aanvragen")
        .select("id, aangevraagd_op, status, run_url")
        .in("status", LOPEND)
        .order("aangevraagd_op", { ascending: false })
        .limit(1);
      if (error) throw new Error("Kan de aanvraag niet lezen.");
      return data?.[0] ?? null;
    },
    async zetGestopt(id: number) {
      const { error } = await db.from("crawl_aanvragen")
        .update({ status: "gestopt", bijgewerkt_op: new Date().toISOString() })
        .eq("id", id)
        .in("status", LOPEND);
      if (error) throw new Error("Kan de aanvraag niet bijwerken.");
    },
  };

  const github: GitHub = (pad, init) =>
    fetch(`https://api.github.com${pad}`, {
      method: init?.method ?? "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SpellingSpeurneus",
      },
    });

  try {
    const uitkomst = await stopCrawl(opslag, github, REPO, WORKFLOW);
    return antwoord(uitkomst.status, uitkomst.lichaam);
  } catch (fout) {
    return antwoord(500, { fout: (fout as Error).message });
  }
});
