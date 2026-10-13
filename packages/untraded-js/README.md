# untraded

Open, transparent Counter-Strike 2 match metrics.

> **Early preview.** This package will host the open metrics library of [Untraded](https://github.com/untraded), a self-hostable CS2 demo analyzer and coach. Every metric ships with its formula, its version and its tests.

## Available now

```js
import { ratingHltv1 } from "untraded";

ratingHltv1({ rounds: 24, kills: 25, deaths: 15, multikills: { 1: 10, 2: 4, 3: 1, 4: 1 } });
```

`ratingHltv1` implements HLTV's public Rating 1.0 formula:

```
(KillRating + 0.7 × SurvivalRating + MultiKillRating) / 2.7

KillRating      = (kills / rounds) / 0.679
SurvivalRating  = ((rounds − deaths) / rounds) / 0.317
MultiKillRating = ((1K + 4×2K + 9×3K + 16×4K + 25×5K) / rounds) / 1.277
```

Untraded is not affiliated with HLTV or Valve.

## License

MIT
