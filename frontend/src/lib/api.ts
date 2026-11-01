import type { Utilisateur } from "./types";

const CLE_REFRESH = "sdm.refresh";
let acces: string | null = null;
let rafraichissementEnCours: Promise<boolean> | null = null;
let surDeconnexion: (() => void) | null = null;

export class ErreurApi extends Error {
  constructor(public statut: number, message: string, public code?: string) {
    super(message);
  }
}

/** Jeton de renouvellement de ce navigateur (sert à repérer « cet appareil » dans la liste des sessions). */
export function jetonRafraichissement(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(CLE_REFRESH);
}

export function enregistrerSurDeconnexion(fn: () => void) {
  surDeconnexion = fn;
}

function messageDepuis(corps: unknown, statut: number): { message: string; code?: string } {
  if (corps && typeof corps === "object" && "detail" in corps) {
    const { detail, code } = corps as { detail: unknown; code?: string };
    if (typeof detail === "string") return { message: detail, code };
    if (Array.isArray(detail)) return { message: "Certaines valeurs sont invalides. Vérifiez les champs saisis.", code };
  }
  if (statut === 429) return { message: "Trop de tentatives. Réessayez dans quelques minutes." };
  return { message: `Erreur ${statut}. Réessayez, ou vérifiez que le serveur tourne.` };
}

async function appeler(chemin: string, methode: string, corps?: unknown, jeton?: string | null): Promise<Response> {
  const entetes: Record<string, string> = {};
  if (corps !== undefined) entetes["Content-Type"] = "application/json";
  if (jeton) entetes["Authorization"] = `Bearer ${jeton}`;
  try {
    return await fetch(chemin, { method: methode, headers: entetes, body: corps === undefined ? undefined : JSON.stringify(corps) });
  } catch {
    throw new ErreurApi(0, "Le serveur ne répond pas. Vérifiez que l'API tourne sur le port 8000.");
  }
}

function memoriser(acces_: string, refresh: string) {
  acces = acces_;
  localStorage.setItem(CLE_REFRESH, refresh);
}

async function tenterRafraichissement(): Promise<boolean> {
  const refresh = typeof window === "undefined" ? null : localStorage.getItem(CLE_REFRESH);
  if (!refresh) return false;
  if (!rafraichissementEnCours) {
    rafraichissementEnCours = (async () => {
      const r = await appeler("/api/v1/auth/rafraichir", "POST", { refresh_token: refresh });
      if (!r.ok) {
        acces = null;
        localStorage.removeItem(CLE_REFRESH);
        return false;
      }
      const c = await r.json();
      memoriser(c.access_token, c.refresh_token);
      return true;
    })().finally(() => {
      rafraichissementEnCours = null;
    });
  }
  return rafraichissementEnCours;
}

export async function api<T>(chemin: string, options: { methode?: string; corps?: unknown } = {}): Promise<T> {
  const methode = options.methode ?? "GET";
  let r = await appeler(chemin, methode, options.corps, acces);
  if (r.status === 401 && (await tenterRafraichissement())) {
    r = await appeler(chemin, methode, options.corps, acces);
  }
  if (r.status === 401) {
    surDeconnexion?.();
  }
  if (!r.ok) {
    const corps = await r.json().catch(() => null);
    const { message, code } = messageDepuis(corps, r.status);
    throw new ErreurApi(r.status, message, code);
  }
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T);
}

export async function connexion(email: string, motDePasse: string): Promise<Utilisateur> {
  const r = await appeler("/api/v1/auth/connexion", "POST", { email, mot_de_passe: motDePasse });
  const corps = await r.json().catch(() => null);
  if (!r.ok) {
    const { message, code } = messageDepuis(corps, r.status);
    throw new ErreurApi(r.status, message, code);
  }
  memoriser(corps.access_token, corps.refresh_token);
  return corps.utilisateur as Utilisateur;
}

export async function inscription(email: string, nom: string, motDePasse: string): Promise<void> {
  const r = await appeler("/api/v1/auth/inscription", "POST", { email, nom, mot_de_passe: motDePasse });
  if (!r.ok) {
    const corps = await r.json().catch(() => null);
    const { message, code } = messageDepuis(corps, r.status);
    throw new ErreurApi(r.status, message, code);
  }
}

export async function restaurerSession(): Promise<Utilisateur | null> {
  if (!(await tenterRafraichissement())) return null;
  try {
    return await api<Utilisateur>("/api/v1/moi");
  } catch {
    return null;
  }
}

export async function deconnexion(): Promise<void> {
  const refresh = localStorage.getItem(CLE_REFRESH);
  acces = null;
  localStorage.removeItem(CLE_REFRESH);
  if (refresh) await appeler("/api/v1/auth/deconnexion", "POST", { refresh_token: refresh }).catch(() => undefined);
}
