// De logica van "een crawl stoppen", los van Supabase en GitHub zodat ze te testen is
// (zie stoppen.test.ts). index.ts koppelt hem aan de echte diensten.

export interface Aanvraag {
  id: number;
  aangevraagd_op: string;
  status: string;
  run_url: string | null;
}

export interface Opslag {
  /** De nieuwste aanvraag die nog loopt (aangevraagd, crawlen of publiceren), of null. */
  actieveAanvraag(): Promise<Aanvraag | null>;
  /** Zet de aanvraag op 'gestopt', maar alleen als hij nog loopt. */
  zetGestopt(id: number): Promise<void>;
}

export type GitHub = (
  pad: string,
  init?: { method?: string },
) => Promise<{ status: number; json(): Promise<any> }>;

export interface Antwoord {
  status: number;
  lichaam: Record<string, unknown>;
}

const LOPEND = ["queued", "in_progress", "waiting", "pending", "requested"];

/** Het nummer van de run uit de link die de crawler heeft opgeslagen. */
export function runIdUit(url: string | null): string | null {
  const treffer = url?.match(/\/actions\/runs\/(\d+)/);
  return treffer ? treffer[1] : null;
}

/**
 * Zoekt de run als de crawler zijn link nog niet heeft opgeslagen (de eerste seconden na het
 * starten). Alleen als er precies één lopende run is die na de aanvraag is gestart; bij twijfel
 * stoppen we niets, want het kan een run zijn die iemand anders in GitHub heeft gestart.
 */
export async function vindRun(
  github: GitHub,
  repo: string,
  workflow: string,
  aanvraag: Aanvraag,
): Promise<string | null> {
  const antwoord = await github(
    `/repos/${repo}/actions/workflows/${workflow}/runs?event=workflow_dispatch&per_page=20`,
  );
  if (antwoord.status !== 200) return null;
  const { workflow_runs } = await antwoord.json();
  const vanaf = Date.parse(aanvraag.aangevraagd_op) - 2 * 60_000;
  const kandidaten = (workflow_runs ?? []).filter(
    (run: { status: string; created_at: string }) =>
      LOPEND.includes(run.status) && Date.parse(run.created_at) >= vanaf,
  );
  return kandidaten.length === 1 ? String(kandidaten[0].id) : null;
}

export async function stopCrawl(
  opslag: Opslag,
  github: GitHub,
  repo: string,
  workflow: string,
): Promise<Antwoord> {
  const aanvraag = await opslag.actieveAanvraag();
  if (!aanvraag) return { status: 404, lichaam: { fout: "Er loopt geen crawl." } };

  // Tijdens het opslaan stoppen laat een half resultaat achter dat als laatste crawl zou
  // gelden. Dat duurt maar even; wacht dan tot hij klaar is.
  if (aanvraag.status === "publiceren") {
    return {
      status: 409,
      lichaam: { fout: "De crawl slaat het resultaat op; stoppen kan nu niet meer." },
    };
  }

  const runId = runIdUit(aanvraag.run_url) ?? await vindRun(github, repo, workflow, aanvraag);
  if (!runId) {
    return {
      status: 409,
      lichaam: {
        fout: "De run in GitHub is niet met zekerheid te vinden. Stop hem daar zelf, bij Actions.",
      },
    };
  }

  const antwoord = await github(`/repos/${repo}/actions/runs/${runId}/cancel`, { method: "POST" });
  if (antwoord.status === 202) {
    await opslag.zetGestopt(aanvraag.id);
    return { status: 200, lichaam: { ok: true } };
  }
  if (antwoord.status === 409) {
    return { status: 409, lichaam: { fout: "Deze crawl is al klaar of wordt al gestopt." } };
  }
  return {
    status: 502,
    lichaam: { fout: `GitHub weigerde het stoppen (${antwoord.status}).` },
  };
}
