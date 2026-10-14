# Rapport S0.4 — démos pro

*Rempli le 14/10/2026 après `just spike-parsing` et `just spike-rounds` sur 11 démos, sous Linux (Python 3.14, demoparser2 0.42.0).*

## Résultat
- [x] 10 démos pro dans le corpus : **11 démos** (4 matchs, 3 LAN et 1 online, 4 organisateurs).
- [ ] 7 cartes couvertes : **6 seulement** (mirage, inferno, ancient, dust2, cache, anubis). La 7e carte du pool manque.
- [x] Elles se parsent comme les démos MM : aucune erreur, mêmes props (usercmd compris).
- [ ] Source utilisable pour la version hébergée : **pas encore**. Les démos du spike ont été téléchargées à la main depuis les pages de match HLTV, pour un test interne, sans redistribution.

## Corpus
| Organisateur | Format | Cartes | Patchs | Taille `.dem` |
|---|---|---|---|---|
| ESL Pro League | LAN | 3 | 14188 | 326 à 464 Mo |
| StarLadder StarSeries | LAN | 2 | 14181 | 284 à 324 Mo |
| FiSSURE Playground | LAN | 3 | 14181 | 373 à 405 Mo |
| CCT | online | 3 | 14190 | 345 à 362 Mo |

- Tous les matchs sont postérieurs au 09/09/2026.
- HLTV livre une archive `.rar` par match, avec un `.dem` par carte ; il n'y a pas de `.dem` compressé à décompresser.
- Une démo pro fait **284 à 464 Mo** (médiane 354 Mo) : comme les plus grosses démos MM, pour 17 à 29 rounds.

## Mesures
Médiane / maximum sur 11 démos :

| Parse des événements (s) | Parse plein (s) | Parse 16 Hz (s) | Parquet 16 Hz (Mo) | RAM max (Mo) |
|---|---|---|---|---|
| 2,6 / 3,3 | 5,3 / 8,6 | 4,6 / 8,6 | 3,3 / 4,9 | 1 631 / 1 980 |

- C'est environ deux fois plus que les démos MM (2,4 / 3,9 s en parse plein), proportionnellement à la taille.
- La RAM atteint **2 Go** pour la plus grosse démo (464 Mo, 28 rounds). Une carte en prolongations dépasserait 500 Mo et approcherait le budget de 3 Go : le worker devra parser par colonnes ou par tranches de ticks.

## Contenu des démos
| Question | Réponse |
|---|---|
| usercmd présents dans les démos pro ? | **Oui** : `usercmd_viewangle_*`, `usercmd_mouse_d*` (90 % non nuls), `usercmd_buttonstate_1` (86 %), `usercmd_input_history` (100 %). `usercmd_subtick_moves` absent, comme en MM. |
| Mêmes props qu'en MM ? | **Oui**, toutes présentes à 96-100 %, sauf `active_weapon_name` et `accuracy_penalty` (81 %, nuls quand le joueur est mort). `aim_punch_angle` et `inaccuracy` absents, comme en MM après le 09/09/2026. |
| Tickrate | 64 ticks/s, comme en MM (header sans tickrate, à calculer). |
| Nom des équipes | `team_clan_name` rempli en LAN (ESL, StarLadder, FiSSURE), **vide sur CCT**. |
| `server_name` | Nom de l'organisateur en LAN (« ESL Match Server #1 », « StarLadder StarSeries Fall 2026 », « Counter-Strike 2 »), un hash sur CCT. Inutilisable pour identifier la source. |

### Différences avec les démos MM
- **`round_officially_ended` n'existe pas** dans les démos pro, alors qu'il est émis (deux fois par round) en MM. Comme `round_start` et `round_end` manquent aussi, il ne reste que `round_freeze_end` comme événement de round.
- **`player_blind` n'existe pas** dans les démos pro. La prop `flash_duration` le remplace : juste après chaque `flashbang_detonate`, elle marque 2 à 3 joueurs aveuglés par flash en moyenne. L'attribution (qui a aveuglé qui) se fera en croisant le lanceur du flash et la hausse de `flash_duration`.

### Découpage des rounds
| Organisateur | `round_freeze_end` = rounds joués = score ? |
|---|---|
| ESL, StarLadder, FiSSURE (8 démos) | **Oui**, partout. |
| CCT, carte 1 et carte 2 | **Non** : la démo commence pendant le round 1. Le freeze end du round 1 manque (21 pour 22 rounds, 17 pour 18). |
| CCT, carte 3 | **Non** : un freeze end de plus pendant l'échauffement (30 pour 29 rounds). |

C'est le défaut connu de certaines démos d'organisateurs (demoparser2 #59). Règles pour le moteur de stats :
1. ignorer les `round_freeze_end` pendant l'échauffement (`is_warmup_period`) ;
2. numéroter les rounds avec `total_rounds_played` des gamerules, pas en comptant les événements ;
3. détecter un round 1 incomplet (premier round vivant ≠ 1) et l'exclure des métriques, ou marquer la démo comme incomplète ;
4. déduire le vainqueur de chaque round de la hausse de `team_rounds_total`, puisqu'aucun événement de fin de round n'existe.

## Décision
**GO technique.** Les démos pro se parsent sans erreur, dans le budget, avec les mêmes données que les démos MM, usercmd compris. Le moteur de stats doit découper les rounds à partir de l'état des gamerules et non des événements, et reconstruire les aveuglements à partir de `flash_duration`.

Restent ouverts :
- la 7e carte du pool, à ajouter au corpus ;
- le choix d'une source de démos pro pour la version hébergée, à trancher avant la revue go/no-go de fin de phase 0.
