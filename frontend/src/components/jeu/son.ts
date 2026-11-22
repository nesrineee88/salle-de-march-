let contexte: AudioContext | null = null;

/** Un son bref, fabriqué sur place : aucun fichier audio à charger. Sans audio disponible, le jeu continue en silence. */
export function bip(actif: boolean, frequence = 440, duree = 0.12, volume = 0.05) {
  if (!actif) return;
  try {
    contexte ??= new AudioContext();
    if (contexte.state === "suspended") void contexte.resume();
    const oscillateur = contexte.createOscillator();
    const gain = contexte.createGain();
    const t = contexte.currentTime;
    oscillateur.frequency.value = frequence;
    gain.gain.setValueAtTime(volume, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + duree);
    oscillateur.connect(gain).connect(contexte.destination);
    oscillateur.start();
    oscillateur.stop(t + duree);
  } catch {
    /* pas de sortie audio */
  }
}
