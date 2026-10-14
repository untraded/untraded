# Rapport S0.3 — démo FACEIT par extension navigateur

*Rempli le 14/10/2026 après un test réel sous Linux (Firefox, extension chargée temporairement, `just spike-faceit-server`).*

## Résultat
- [x] 1 démo FACEIT arrivée sur le serveur local via l'extension : **oui**, du premier coup.
- [x] Avis écrit sur le risque lié aux conditions d'utilisation : voir plus bas.

## Comment FACEIT sert les démos
1. Le bouton « Watch demo » de la page de match lance une vérification **Cloudflare Turnstile**, en place depuis avril 2024 au moins.
2. `POST https://www.faceit.com/api/download/v2/demos/download-url` reçoit `resource_url`, l'URL publique de la démo (`demos-*.backblaze.faceit-cdn.net/cs2/<id>.dem.zst`, la même que le `demo_url` de la Data API).
3. La réponse `payload.download_url` est une **URL présignée Backblaze B2** (S3), **valable 299 s**. Le navigateur la télécharge : un `.dem.zst`.

Sans Turnstile, impossible d'obtenir l'URL signée. Le `demo_url` de la Data API seul ne suffit pas.

## Ce que fait l'extension
- Manifest V3, un seul fichier JavaScript, sans build. Le même manifeste fonctionne sous Chrome (`service_worker`) et Firefox (`scripts`).
- Permissions : `downloads`, et l'hôte `http://127.0.0.1/*` pour le serveur local.
- Elle **n'appelle jamais FACEIT, ne lit pas la page et n'affiche pas Turnstile**. Le joueur clique lui-même sur « Watch demo » et passe la vérification. L'extension écoute `downloads.onCreated`, ne retient que les URL HTTPS des hôtes FACEIT et Backblaze au chemin `/cs2/<id>.dem.zst|gz`, et envoie l'URL au serveur.
- Le serveur local (stdlib Python) répond 202 tout de suite, télécharge en arrière-plan (reprise par `Range`), vérifie la signature de démo CS2 après décompression zstd, et n'écrit jamais l'URL signée sur disque.

## Mesures (1 démo)
| Étape | Valeur |
|---|---|
| Début du téléchargement dans le navigateur → URL reçue par le serveur | 0,16 s |
| Validité restante de l'URL à réception | 298 s sur 299 |
| Téléchargement serveur | 241 Mo (`.dem.zst`) en 15,1 s, soit 16 Mo/s, sans coupure |
| Après décompression | 332 Mo, signature `PBDEMS2` OK |
| Parsing (script S0.2) | 5,2 s, 1,6 Go de RAM, mêmes événements manquants que les autres démos FACEIT |

La fenêtre de 5 minutes est large si le serveur démarre le téléchargement à réception. Elle ne l'est plus s'il le met en file d'attente : l'ingestion d'une URL FACEIT doit être prioritaire, ou bien c'est l'extension qui envoie le fichier.

## Limites constatées
- **Le navigateur télécharge aussi la démo** (240 Mo en double). L'extension pourrait annuler ce téléchargement, mais le joueur veut parfois garder le fichier : à proposer en option.
- L'extension voit **tous** les téléchargements du navigateur pour les filtrer. Elle ne transmet que les démos FACEIT, mais il faudra le dire clairement dans la description.
- Firefox ne garde une extension chargée temporairement que jusqu'à sa fermeture. Une version utilisable devra être signée sur AMO et publiée sur le Chrome Web Store.
- Si FACEIT change d'hôte de stockage ou de format d'URL, le filtre casse sans erreur visible : à surveiller avec un badge et des logs.

## Risque lié aux conditions d'utilisation
Ceci n'est pas un avis juridique. Conditions FACEIT en vigueur au 01/09/2026 :
- §34.2 : le contenu téléchargé est réservé à un usage personnel et non commercial ;
- §36 d : pas de scripts automatisés pour collecter des données ;
- §37.1 : pas de contournement des contrôles de sécurité, pas d'extension qui « interfere » avec le site.

Pour **une extension open source que le joueur installe pour sa propre instance**, le risque est **faible à moyen** :
- elle ne contourne rien (Turnstile reste résolu par un humain) ;
- elle n'automatise aucune collecte (un clic, une démo, celle du joueur) ;
- elle n'interfère pas avec la page ;
- une extension tierce plus intrusive (elle affiche Turnstile elle-même et appelle l'API interne) est publiée sur AMO et le Chrome Web Store depuis 2024, sans retrait connu.

Le risque principal est **technique** : FACEIT peut modifier son site à tout moment. L'upload manuel du fichier reste la solution de secours.

## Décision
**GO pour l'auto-hébergement.** L'extension fonctionne, ne contourne aucune protection et reste minimale (une permission). Pour une instance partagée, la voie principale reste la Downloads API officielle de FACEIT (candidature en cours), avec le webhook `match_demo_ready`.
