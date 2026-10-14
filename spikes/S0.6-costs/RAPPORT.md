# Rapport S0.6 — stockage et CPU par match

*Rempli le 14/10/2026 après `just spike-costs` sur 13 démos (12 pro, 1 FACEIT), sous Linux x86-64 (12 cœurs, Python 3.14, demoparser2 0.42.0). Les démos Premier sont mesurées dans S0.2 ; ce script reste à lancer dessus.*

## Résultat
| Mesure | Médiane | Maximum |
|---|---|---|
| Taille du `.dem` | 354 Mo | 464 Mo |
| zstd niveau 1 : ratio, CPU | 0,842, 2,0 s | 0,857, 4,8 s |
| zstd niveau 3 : ratio, CPU | 0,744, 5,0 s | 0,762, 9,6 s |
| zstd niveau 9 : ratio, CPU | 0,699, 18 s | 0,716, 74 s |
| zstd niveau 19 (1 démo) : ratio, CPU | 0,60, 171 s | |
| Parse + écriture Parquet : CPU | **36 s** | 87 s |
| Parse + écriture Parquet : temps réel | 18 s | 49 s |
| Parquet par match (événements + 24 props à 16 Hz) | **5,9 Mo** | 8,2 Mo |

Le maximum vient d'une seule démo (464 Mo), mesurée pendant que la machine était chargée. Les médianes sont fiables : 12 démos sur 13 sont entre 29 et 52 s de CPU.

## Constats
1. **Les démos se compressent mal.** zstd ne gagne que 25 à 30 % (niveaux 3 à 9) : le contenu est déjà en grande partie compressé. Valve livre du bz2 (environ 0,67 du `.dem`, S0.2) et FACEIT du zstd (0,725) : **stocker le fichier tel qu'il arrive** coûte zéro CPU et prend autant de place qu'une recompression au niveau 9. Ne pas recompresser.
2. **Le temps CPU vaut environ 2 fois le temps réel.** demoparser2 parallélise : un serveur partagé facture le CPU, pas le temps réel. Les temps de S0.2 sont des temps réels.
3. **Le Parquet est petit** : environ 6 Mo par match, soit **60 fois moins que la démo**. Les événements pèsent moins de 0,1 Mo ; l'essentiel est la table des ticks à 16 Hz.
4. Le parsing de S0.4 (16 props, sans événements ni écriture) prenait 4,6 s de temps réel. Ici, 24 props (dont `inventory` et les usercmd), les événements et l'écriture Parquet prennent 18 s : **chaque prop ajoutée se paie**. Le choix des props stockées est un levier de coût.

## Ce que le modèle de coûts doit retenir
- Stockage d'un match : environ **0,70 × la taille du `.dem`** pour la démo brute, plus **6 Mo** de Parquet.
- CPU d'un match : environ **36 s** de parsing et d'écriture, plus la décompression bz2 (environ 6 s, S0.2), plus le calcul des métriques (pas encore mesuré).
- RAM : 2 Go au maximum par parsing (S0.2, S0.4).

## Reste à mesurer
- Les démos Premier avec ce script (taille médiane et CPU) : sur le PC Windows, `just spike-costs <inbox>`.
- Le même script sur ARM (serveur Oracle), pour connaître l'écart de performance avec x86.
- Le coût du calcul des métriques, en phase 1.

## Décision
**GO.** Le coût de calcul par match est faible ; le coût dominant sera le stockage des démos brutes, qui dépend surtout de leur durée de conservation.
