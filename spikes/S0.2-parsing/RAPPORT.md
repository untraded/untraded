# Rapport S0.2 — parsing, performances, contenu des démos

*Rempli le 13/10/2026 après `just spike-parsing` sur 28 démos, sous Windows 11 (Python 3.14, demoparser2 0.42.0).*

## Résultat
- [x] Parsing « utile » (16 Hz) < 60 s et < 3 Go par démo : **3,4 s et 1,7 Go au pire**
- [x] Démos post-09/09/2026 parsées sans erreur : 21 démos en patch 14176 à 14190, aucune erreur

## Corpus
| Source | Démos | Patchs | Taille `.dem` |
|---|---|---|---|
| Valve, téléchargées par le client CS2 (`.dem`) | 8 | 14067 → 14190 (02/2025 → 10/2026) | 60 à 503 Mo |
| Valve, téléchargées par le bot S0.1 (`.dem.bz2`) | 18 | 14190 | 34 à 364 Mo |
| FACEIT (`.dem`) | 2 | 14176, 14181 | 328 à 332 Mo |
| Scrim, pro | 0 | | |

Cartes : dust2, nuke, inferno, ancient, mirage. Les noms de fichiers et identifiants de match ne sont pas reproduits ici (données personnelles) ; le détail par démo est dans `out/report.md`, ignoré par Git.

## Mesures
Médiane / maximum par source :

| Source | Décompression (s) | Parse plein (s) | Parse 16 Hz (s) | Parquet 16 Hz (Mo) | RAM max (Mo) |
|---|---|---|---|---|---|
| Valve, client | — | 2,4 / 3,9 | 1,8 / 3,3 | 2,7 | 1 261 / 1 581 |
| Valve, bot (bz2) | 6,2 / 12,0 | 2,2 / 4,3 | 1,7 / 3,4 | 2,1 | 890 / 1 710 |
| FACEIT | — | 3,5 / 3,6 | 2,7 / 2,8 | 3,5 | 1 403 / 1 427 |

- La RAM croît avec la taille de la démo sans dépasser 1,7 Go (364 Mo de `.dem`).
- La décompression bz2 en Python coûte plus cher que le parsing (jusqu'à 12 s contre 4 s). À paralléliser ou à faire en streaming dans le worker.
- Un `.dem.bz2` fait environ 2/3 du `.dem`.

## Contenu des démos
| Question | Réponse |
|---|---|
| `bullet_impact` présent ? | **Non**, dans aucune démo. Utiliser `weapon_fire` / `fire_bullets` (présents) et `player_hurt` pour les impacts sur joueur. |
| `inventory`, `accuracy_penalty`, `spotted` exploitables ? | **Oui** : `inventory` 100 % non nul, `spotted` et `approximate_spotted_by` 99-100 %, `accuracy_penalty` 71 % (nul quand le joueur est mort, comme `active_weapon_name`). `inaccuracy` n'existe pas. |
| usercmd présents dans les démos MM ? FACEIT ? pro ? | **Oui** en MM et FACEIT : `usercmd_viewangle_*`, `usercmd_mouse_d*`, `usercmd_buttonstate_1` (83-86 % non nuls), `usercmd_input_history` (100 %). `usercmd_subtick_moves` absent partout. Pro : pas encore testé (S0.4). |
| Tickrate lu dans le header ? | **Non.** Le header ne contient ni tickrate ni mode de jeu (`demo_version_name`, `patch_version`, `map_name`, `server_name`…). Mesuré : `max_tick` / durée du match (GC) = 64,4 à 66,2 sur 18 démos, soit **64 ticks/s** plus l'échauffement. À calculer à chaque démo, jamais supposer. |

Autres constats :
- **`round_start`, `round_end` et `item_purchase` n'existent pas** dans les démos CS2. Les rounds se découpent avec `round_freeze_end` (un par round) et `round_officially_ended`, **émis deux fois par round** sauf au dernier (2n − 2). Les achats se déduisent des changements d'`inventory` et de `balance`.
- **`aim_punch_angle` a disparu après le 09/09/2026** : présent dans les 7 démos jusqu'au patch 14141, absent des 21 démos à partir du patch 14176. À ne pas utiliser dans une métrique.
- Le mode de jeu n'est pas dans la démo : le Premier se distingue par les données du GC (S0.1), FACEIT par `server_name`. Les matchs Wingman (deux démos de 34-38 Mo terminées à 9-3) doivent être écartés avant le parsing.
- Le script plantait sous Windows sur une flèche non ASCII et mesurait toujours 0 Mo de RAM : corrigé (#10). `out/report.md` est encore écrit dans l'encodage de la console Windows (cp1252) au lieu d'UTF-8 : à corriger.

## demoparser2 0.42.0 vs `main`
Non testé : 0.42.0 n'a planté sur aucune démo, de février 2025 à octobre 2026. À refaire seulement si une mise à jour de CS2 casse le parsing.

## Décision
**GO.** demoparser2 0.42.0 est assez rapide (moins de 5 s par démo, décompression comprise moins de 20 s) et assez sobre (moins de 2 Go) pour le worker. Contraintes pour le moteur de stats :
1. découper les rounds sans `round_start`/`round_end`, et dédoublonner `round_officially_ended` ;
2. déduire les achats de l'inventaire ;
3. calculer le tickrate pour chaque démo ;
4. ne pas dépendre de `aim_punch_angle`, `inaccuracy`, `usercmd_subtick_moves` ni `bullet_impact` ;
5. filtrer le mode de jeu (Wingman) avant le parsing.

Reste à couvrir : démos de scrim et démos pro (S0.4).
