# Rapport S0.1 — chaîne Valve

*Rapport intermédiaire (J0, 13/10/2026) : premier lancement réel sous Windows, 18 matchs rattrapés d'un coup. L'exécution horaire sur 7 jours (jusqu'au 20/10/2026) complètera les lignes marquées « J7 ».*

## Résultat
- [x] 10 matchs consécutifs récupérés sans intervention : **18 sur 18** (10/10 → 13/10/2026), après une seule saisie du code Steam Guard
- [ ] Stabilité sur 7 jours d'exécution horaire (J7)

## Mesures
| Mesure | Valeur |
|---|---|
| Délai fin de match → démo disponible (médiane, max) | **2,6 min / 3,7 min**, déduit de l'expiration GCS (voir Surprises) ; mesure directe à J7 |
| Connexion GC (médiane) | **1,7 s** avec le refresh token ; 25 s à la première connexion (licence CS2 + Steam Guard) |
| Requête de match GC (médiane, échecs) | **0,29 s** (max 0,35 s), 0 échec sur 18 |
| Taille .bz2 (médiane) | **125 Mo** (23 à 245 Mo) ; un `.dem` décompressé fait ~1,5× le `.bz2` (113 → 172 Mo) |
| Téléchargement (médiane, max) | **69 s / 335 s** par démo ; débit de 0,42 à 18,5 Mo/s (médiane 1,3 Mo/s) |
| Démos expirées ou absentes | 0 (toutes < 4 jours) |
| Erreurs de chaîne (412, 403, 429) | Un 412 sur un share code de plus d'un mois (attendu) ; aucun 403 ni 429 |
| Compte bot limité : OK ? | **Oui** : compte neuf sans achat, la licence gratuite CS2 est accordée par `requestFreeLicense` et le GC répond |

## Surprises
1. **Téléchargements bridés et coupés.** Les serveurs `replayNNN.valve.net` sont adossés à Google Cloud Storage. Chaque connexion est limitée (50-170 Ko/s observés aux heures creuses, pour une ligne à 50 Mo/s) et coupée net environ tous les **8,4 Mo** (`TypeError: terminated`). Le débit varie énormément d'une démo à l'autre (de 0,42 à 18,5 Mo/s). La reprise par `Range` règle le problème : 7 démos sur 18 ont eu besoin de 2 à 5 tentatives, aucune n'a échoué (#9).
2. **Plusieurs connexions s'additionnent.** 8 requêtes `Range` en parallèle cumulent leurs débits ; un des morceaux est même arrivé à 8,4 Mo/s (probablement déjà en cache). Piste pour la version hébergée : téléchargement segmenté.
3. **L'expiration est dans les en-têtes.** `x-goog-custom-time` vaut exactement « envoi de la démo + 30 jours ». On connaît donc la date de suppression de chaque démo, et on peut en déduire quand Valve l'a envoyée : 0,9 à 3,7 min après la fin du match.
4. **Le délai de 60 s de connexion comptait le temps de saisie du code Steam Guard** : le premier essai a échoué pendant que l'utilisateur tapait le code. Corrigé (#9).
5. **Matchs hors périmètre dans la chaîne.** Elle renvoie aussi les modes non ciblés : 2 matchs de 23-25 Mo terminés à 9-3 (Wingman probable) et un match arrêté à 7-0. Il faudra filtrer le mode avant de parser (`game_type`/`game_mode` du GC, à vérifier).

## Décision
**Provisoire : GO.** La chaîne share code → GC → démo fonctionne sans intervention, rapidement et avec un compte bot gratuit. Le seul vrai obstacle (débit de Valve) est contourné par la reprise, et le téléchargement segmenté peut l'accélérer. Décision définitive après les 7 jours d'exécution horaire.
