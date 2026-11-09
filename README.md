# Sayand's Collections — Nuvio / Stremio add-on

Install in Nuvio → Add-ons → Install from URL:

```
https://sayandp.github.io/nuvio-collections/manifest.json
```

32 catalogs: favourites, For You recommendations, "Because you like…", sitcoms by era (70s–2020s + India),
Netflix / Prime / Hulu & FX / HBO / Apple TV+ originals, international & British series, After Dark 18+, and more.

## Update
1. Edit `FAV_SERIES`, `FAV_MOVIES` or the `DB` table in `tools/build.py`
2. `python tools/build.py --resolve`  (verifies/fixes IMDb IDs via Cinemeta, needs internet)
3. Commit and push — GitHub Pages republishes in about a minute.
