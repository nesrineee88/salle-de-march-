// Pas de "use client" ici : ces chaînes sont lues par le layout serveur.
// Elles s'exécutent avant l'affichage pour éviter un éclair de la mauvaise apparence.
export const SCRIPT_THEME = `try{if(localStorage.getItem("sdm.theme")==="clair"){document.documentElement.dataset.theme="clair"}}catch(e){}`;
export const SCRIPT_APPARENCE = `try{var a=JSON.parse(localStorage.getItem("sdm.apparence")||"{}");var d=document.documentElement;d.dataset.modele=a.modele||"wallet";d.dataset.palette=a.palette||"nuit";d.dataset.fond=a.fond||"vivant";if(a.densite)d.dataset.densite=a.densite}catch(e){}`;
