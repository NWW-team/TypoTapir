// De controle op het verzoek om een naam naar de spelfouten te verplaatsen, los van Supabase
// zodat ze te testen is (zie verplaatsen.test.ts). index.ts koppelt hem aan de database.

export type Actie = "verplaatsen" | "terugzetten";

export interface Geldig {
  ok: true;
  actie: Actie;
  woord: string;
}
export interface Ongeldig {
  ok: false;
  fout: string;
}

/** Het maximum aantal wijzigingen per uur, over alle bezoekers samen. */
export const MAX_PER_UUR = 300;

/**
 * Controleert de invoer. Het gaat om één los woord (een naam), geen zin: geen witruimte of
 * besturingstekens, en niet langer dan de database toelaat.
 */
export function valideer(invoer: { actie?: unknown; woord?: unknown }): Geldig | Ongeldig {
  const { actie } = invoer;
  const woord = typeof invoer.woord === "string" ? invoer.woord.trim() : "";
  if (actie !== "verplaatsen" && actie !== "terugzetten") return { ok: false, fout: "Onbekende actie." };
  if (woord.length < 1 || woord.length > 100) return { ok: false, fout: "Een woord is 1 tot 100 tekens." };
  if (/[\s\p{C}]/u.test(woord)) return { ok: false, fout: "Dit is geen los woord." };
  return { ok: true, actie, woord };
}

/** Of er in het afgelopen uur al te veel is gewijzigd. */
export const teVeel = (aantalVerplaatst: number, aantalTeruggezet: number): boolean =>
  aantalVerplaatst + aantalTeruggezet >= MAX_PER_UUR;
