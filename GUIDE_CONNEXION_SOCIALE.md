# Connexion avec Google et GitHub

Les boutons sont déjà dans la page de connexion. Ils restent grisés tant que le serveur n'a pas les identifiants du fournisseur.
Les clés se mettent dans des **variables d'environnement**, jamais dans Git.

## 1. Adresse de retour (à donner aux deux fournisseurs)

En développement : `http://localhost:3000/api/v1/auth/oauth/google/retour` (Google) et `.../github/retour` (GitHub).
Le front relaie `/api` vers le backend, donc l'adresse publique est celle du site (port 3000).

## 2. GitHub
1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App.
2. Homepage URL : `http://localhost:3000`. Authorization callback URL : l'adresse GitHub ci-dessus.
3. Notez le Client ID, générez un Client secret.

## 3. Google
1. console.cloud.google.com → APIs & Services → Credentials → Create credentials → OAuth client ID (type « Web application »).
2. Authorized redirect URI : l'adresse Google ci-dessus. (Configurez d'abord l'écran de consentement OAuth, en mode « Test » avec vos adresses e-mail d'équipe.)
3. Notez le Client ID et le Client secret.

## 4. Variables d'environnement (PowerShell, avant de lancer uvicorn)
```powershell
$env:SDM_URL_FRONT = "http://localhost:3000"
$env:SDM_GITHUB_CLIENT_ID = "..."
$env:SDM_GITHUB_CLIENT_SECRET = "..."
$env:SDM_GOOGLE_CLIENT_ID = "..."
$env:SDM_GOOGLE_CLIENT_SECRET = "..."
```
Relancez le backend : les boutons deviennent actifs.

## Comment ça marche (pour la soutenance)
- Flux « code d'autorisation » côté serveur ; le paramètre `state` est signé et expire en 10 minutes (anti-falsification).
- On n'accepte que une adresse e-mail **vérifiée** par Google/GitHub. Le compte est retrouvé par e-mail, ou créé (rôle apprenant, mot de passe aléatoire inutilisable).
- Aucun jeton du fournisseur n'est conservé. Le navigateur reçoit uniquement notre jeton de session, dans le fragment d'URL (`#session=`), qui n'est jamais envoyé à un serveur.
- Chaque connexion est inscrite dans le journal d'audit (`via: google` ou `github`).
