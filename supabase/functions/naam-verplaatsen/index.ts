// Een naam die verkeerd gespeld is, verplaatsen naar de spelfouten (en weer terugzetten).
// Schrijft in de tabel `naam_is_spelfout` met de service-role key die Supabase de functie zelf
// meegeeft; die komt nooit in de browser. Terugzetten verwijdert niets: het zet een datum.
//
// Deze functie is voor iedereen aan te roepen (zie besluit 6 in OVERDRACHT.md). De bescherming is
// strenge invoercontrole en een limiet op het aantal wijzigingen per uur, zoals bij `goedkeuren`.
import { createClient } from "npm:@supabase/supabase-js@2";
import { teVeel, valideer } from "./verplaatsen.ts";

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

  let invoer: { actie?: unknown; woord?: unknown };
  try { invoer = await verzoek.json(); } catch { return antwoord(400, { fout: "Geen geldige JSON." }); }

  const gecontroleerd = valideer(invoer);
  if (!gecontroleerd.ok) return antwoord(400, { fout: gecontroleerd.fout });
  const { actie, woord } = gecontroleerd;

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  const sinds = new Date(Date.now() - 3600_000).toISOString();
  const [a, b] = await Promise.all([
    db.from("naam_is_spelfout").select("id", { count: "exact", head: true }).gte("verplaatst_op", sinds),
    db.from("naam_is_spelfout").select("id", { count: "exact", head: true }).gte("teruggezet_op", sinds),
  ]);
  if (a.error || b.error) return antwoord(500, { fout: "Kan de limiet niet controleren." });
  if (teVeel(a.count ?? 0, b.count ?? 0)) {
    return antwoord(429, { fout: "Te veel wijzigingen in het afgelopen uur. Probeer het later opnieuw." });
  }

  if (actie === "verplaatsen") {
    const { error } = await db.from("naam_is_spelfout").insert({ woord });
    // 23505 = het woord staat er al actief in: klaar.
    if (error && error.code !== "23505") return antwoord(500, { fout: "Opslaan mislukt." });
    return antwoord(200, { ok: true });
  }

  const { error } = await db.from("naam_is_spelfout")
    .update({ teruggezet_op: new Date().toISOString() })
    .ilike("woord", woord.replace(/[\\%_]/g, "\\$&"))
    .is("teruggezet_op", null);
  if (error) return antwoord(500, { fout: "Terugzetten mislukt." });
  return antwoord(200, { ok: true });
});
