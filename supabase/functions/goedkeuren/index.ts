// Woorden en namen goedkeuren of intrekken. Draait met de service-role key die
// Supabase de functie zelf meegeeft; die komt nooit in de browser.
//
// Deze functie is voor iedereen aan te roepen (zie besluit 6 in OVERDRACHT.md).
// De bescherming is daarom: strenge invoercontrole en een limiet op het aantal
// wijzigingen per uur.
import { createClient } from "npm:@supabase/supabase-js@2";

const MAX_PER_UUR = 300;
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

  let invoer: { actie?: unknown; woord?: unknown; soort?: unknown };
  try { invoer = await verzoek.json(); } catch { return antwoord(400, { fout: "Geen geldige JSON." }); }

  const { actie, soort } = invoer;
  const woord = typeof invoer.woord === "string" ? invoer.woord.trim() : "";
  if (actie !== "goedkeuren" && actie !== "intrekken") return antwoord(400, { fout: "Onbekende actie." });
  if (soort !== "woord" && soort !== "naam") return antwoord(400, { fout: "Onbekende soort." });
  if (woord.length < 1 || woord.length > 100) return antwoord(400, { fout: "Een woord is 1 tot 100 tekens." });
  // Geen witruimte of besturingstekens: het gaat om één woord, niet om een zin.
  if (/[\s\p{C}]/u.test(woord)) return antwoord(400, { fout: "Dit is geen los woord." });

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  // Limiet: het aantal wijzigingen in het afgelopen uur, goedgekeurd én ingetrokken.
  const sinds = new Date(Date.now() - 3600_000).toISOString();
  const [a, b] = await Promise.all([
    db.from("goedgekeurd").select("id", { count: "exact", head: true }).gte("goedgekeurd_op", sinds),
    db.from("goedgekeurd").select("id", { count: "exact", head: true }).gte("ingetrokken_op", sinds),
  ]);
  if (a.error || b.error) return antwoord(500, { fout: "Kan de limiet niet controleren." });
  if ((a.count ?? 0) + (b.count ?? 0) >= MAX_PER_UUR) {
    return antwoord(429, { fout: "Te veel wijzigingen in het afgelopen uur. Probeer het later opnieuw." });
  }

  if (actie === "goedkeuren") {
    const { error } = await db.from("goedgekeurd").insert({ woord, soort });
    // 23505 = er is al een actieve rij: het woord is al goedgekeurd, dus klaar.
    if (error && error.code !== "23505") return antwoord(500, { fout: "Opslaan mislukt." });
    return antwoord(200, { ok: true });
  }

  const { error } = await db.from("goedgekeurd")
    .update({ ingetrokken_op: new Date().toISOString() })
    .ilike("woord", woord.replace(/[\\%_]/g, "\\$&"))
    .eq("soort", soort)
    .is("ingetrokken_op", null);
  if (error) return antwoord(500, { fout: "Intrekken mislukt." });
  return antwoord(200, { ok: true });
});
