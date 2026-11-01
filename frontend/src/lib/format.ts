const nombreFr = (min: number, max: number) =>
  new Intl.NumberFormat("fr-FR", { minimumFractionDigits: min, maximumFractionDigits: max });

const F2 = nombreFr(2, 2);
const F3 = nombreFr(3, 3);
const F5 = nombreFr(5, 5);
const F0 = nombreFr(0, 0);
const FQ = nombreFr(0, 4);

/** Prix : plus de décimales pour les petits prix (Dogecoin vaut quelques centimes). */
export function prix(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  const a = Math.abs(n);
  return a >= 10 ? F2.format(n) : a >= 1 ? F3.format(n) : F5.format(n);
}

export const montant = (n: number) => F2.format(n);
export const entier = (n: number) => F0.format(n);
export const quantite = (n: number) => FQ.format(n);

/** Variation signée avec un signe explicite : la couleur n'est jamais la seule information. */
export function variation(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "–";
  const signe = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${signe}${F2.format(Math.abs(n) * 100)} %`;
}

/** Pourcentage à partir d'une fraction : 0,123 devient « 12,3 % ». */
export function pct(n: number | null | undefined, decimales = 1): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "–";
  return `${new Intl.NumberFormat("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(n * 100)} %`;
}

export function pctSigne(n: number | null | undefined, decimales = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "–";
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${pct(Math.abs(n), decimales)}`;
}

export function nombre(n: number | null | undefined, decimales = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "–";
  return new Intl.NumberFormat("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales }).format(n);
}

/** Nom lisible d'un appareil à partir de son « user agent ». */
export function libelleAppareil(agent: string | null): string {
  if (!agent) return "Appareil inconnu";
  const navigateur = /Edg\//.test(agent) ? "Edge" : /OPR\/|Opera/.test(agent) ? "Opera" : /Firefox\//.test(agent) ? "Firefox"
    : /Chrome\//.test(agent) ? "Chrome" : /Safari\//.test(agent) ? "Safari" : "Navigateur";
  const systeme = /Windows/.test(agent) ? "Windows" : /Android/.test(agent) ? "Android" : /iPhone|iPad/.test(agent) ? "iOS"
    : /Mac OS/.test(agent) ? "macOS" : /Linux/.test(agent) ? "Linux" : "";
  return systeme ? `${navigateur} sur ${systeme}` : navigateur;
}

export function signe(n: number): string {
  return n > 0 ? "+" : n < 0 ? "−" : "";
}

export function montantSigne(n: number): string {
  return `${signe(n)}${F2.format(Math.abs(n))}`;
}

/** L'instant simulé est en UTC, sans fuseau : on l'affiche tel quel. Les dates réelles (connexion, audit) peuvent
 *  porter un fuseau explicite (« Z » ou « +00:00 », selon la base de données) : on le respecte. */
export function instantDate(iso: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : `${iso}Z`);
}

const DATE_LONGUE = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const HEURE = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
const DATE_COURTE = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
const DATE_HEURE = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });

export const dateLongue = (iso: string) => DATE_LONGUE.format(instantDate(iso));
export const heure = (iso: string) => HEURE.format(instantDate(iso));
export const dateCourte = (iso: string) => DATE_COURTE.format(instantDate(iso));
export const dateHeure = (iso: string) => DATE_HEURE.format(instantDate(iso));

export const NOMS_CLASSES: Record<string, string> = {
  action: "Actions",
  crypto: "Cryptomonnaies",
  matiere: "Matières premières",
  indice: "Indices de référence",
};
