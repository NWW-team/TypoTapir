// Controles voor stoppen.ts. Draaien met:
//   node supabase/functions/crawl-stoppen/stoppen.test.ts
// (Node 22.18 of nieuwer kan TypeScript zonder opties lezen.) scripts/test.py doet dit ook.
import process from "node:process";
import { runIdUit, stopCrawl, vindRun, type Aanvraag, type GitHub } from "./stoppen.ts";

let fout = 0;
const controle = (naam: string, gelukt: boolean, toelichting = "") => {
  if (!gelukt) fout++;
  console.log(`  ${gelukt ? "OK  " : "FOUT"} ${naam}${toelichting ? " — " + toelichting : ""}`);
};

const REPO = "NWW-team/SpellingSpeurneus";
const nu = Date.parse("2026-10-05T14:00:00Z");
const aanvraag = (extra: Partial<Aanvraag> = {}): Aanvraag => ({
  id: 7,
  aangevraagd_op: new Date(nu).toISOString(),
  status: "crawlen",
  run_url: `https://github.com/${REPO}/actions/runs/555`,
  ...extra,
});

// Een nagemaakte opslag en GitHub, die opschrijven wat ermee gebeurt
function omgeving(opts: { aanvraag?: Aanvraag | null; runs?: unknown[]; annuleer?: number; lijst?: number } = {}) {
  const gebeurd = { gestopt: [] as number[], verzoeken: [] as string[] };
  const opslag = {
    actieveAanvraag: async () => ("aanvraag" in opts ? opts.aanvraag ?? null : aanvraag()),
    zetGestopt: async (id: number) => { gebeurd.gestopt.push(id); },
  };
  const github: GitHub = async (pad, init) => {
    gebeurd.verzoeken.push(`${init?.method ?? "GET"} ${pad}`);
    if (pad.endsWith("/cancel")) return { status: opts.annuleer ?? 202, json: async () => ({}) };
    return { status: opts.lijst ?? 200, json: async () => ({ workflow_runs: opts.runs ?? [] }) };
  };
  return { opslag, github, gebeurd };
}

console.log("Een crawl stoppen");

console.log("De run uit de link");
controle("het nummer staat in de link", runIdUit(`https://github.com/${REPO}/actions/runs/123`) === "123");
controle("zonder link geen nummer", runIdUit(null) === null);
controle("een rare link geeft geen nummer", runIdUit("https://example.com/") === null);

console.log("\nStoppen als de link bekend is");
{
  const e = omgeving();
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("gelukt", a.status === 200 && a.lichaam.ok === true);
  controle("de juiste run wordt geannuleerd",
    e.gebeurd.verzoeken.length === 1 && e.gebeurd.verzoeken[0] === `POST /repos/${REPO}/actions/runs/555/cancel`,
    e.gebeurd.verzoeken.join(" | "));
  controle("de aanvraag staat daarna op gestopt", e.gebeurd.gestopt.join() === "7");
}

console.log("\nGeen crawl, of niet te stoppen");
{
  const e = omgeving({ aanvraag: null });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("geen lopende crawl geeft 404, en er wordt niets geannuleerd",
    a.status === 404 && e.gebeurd.verzoeken.length === 0 && e.gebeurd.gestopt.length === 0);
}
{
  const e = omgeving({ aanvraag: aanvraag({ status: "publiceren" }) });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("tijdens het opslaan wordt niet gestopt",
    a.status === 409 && e.gebeurd.verzoeken.length === 0 && e.gebeurd.gestopt.length === 0);
}

console.log("\nDe run zoeken als de link nog ontbreekt");
{
  const run = { id: 901, status: "in_progress", created_at: new Date(nu + 5_000).toISOString() };
  const e = omgeving({ aanvraag: aanvraag({ run_url: null, status: "aangevraagd" }), runs: [run] });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("precies één lopende run wordt gestopt",
    a.status === 200 && e.gebeurd.verzoeken.at(-1) === `POST /repos/${REPO}/actions/runs/901/cancel`,
    e.gebeurd.verzoeken.join(" | "));
}
{
  const runs = [
    { id: 1, status: "in_progress", created_at: new Date(nu + 1000).toISOString() },
    { id: 2, status: "queued", created_at: new Date(nu + 2000).toISOString() },
  ];
  const e = omgeving({ aanvraag: aanvraag({ run_url: null }), runs });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("bij twee kandidaten wordt niets gestopt",
    a.status === 409 && !e.gebeurd.verzoeken.some((v) => v.startsWith("POST")) && e.gebeurd.gestopt.length === 0);
}
{
  const runs = [
    { id: 3, status: "completed", created_at: new Date(nu + 1000).toISOString() },
    { id: 4, status: "in_progress", created_at: new Date(nu - 3 * 3600_000).toISOString() },
  ];
  const gevonden = await vindRun(omgeving({ runs }).github, REPO, "crawl.yml", aanvraag({ run_url: null }));
  controle("een afgeronde of veel oudere run telt niet mee", gevonden === null, String(gevonden));
}
{
  const e = omgeving({ aanvraag: aanvraag({ run_url: null }), lijst: 500 });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("als GitHub de lijst weigert wordt niets gestopt", a.status === 409 && e.gebeurd.gestopt.length === 0);
}

console.log("\nAls GitHub niet meewerkt");
{
  const e = omgeving({ annuleer: 409 });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("een run die al klaar is geeft 409 en laat de aanvraag met rust",
    a.status === 409 && e.gebeurd.gestopt.length === 0);
}
{
  const e = omgeving({ annuleer: 403 });
  const a = await stopCrawl(e.opslag, e.github, REPO, "crawl.yml");
  controle("een weigering geeft 502 en de aanvraag blijft staan",
    a.status === 502 && e.gebeurd.gestopt.length === 0, JSON.stringify(a.lichaam));
}

console.log(fout ? `\n${fout} controle(s) mislukt.` : "\nAlles goed.");
if (fout) process.exit(1);
