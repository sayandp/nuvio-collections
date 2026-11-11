# Sayand's Collections: Nuvio / Stremio add-on

Install in Nuvio → Add-ons → Install from URL:

```
https://sayandp.github.io/nuvio-collections/manifest.json
```

**175+ shelves, rebuilt every day from TMDB** by a GitHub Action:

- **Charts:** trending today and this week, most popular, all-time top rated, fresh from theatres, new episodes this week
- **Sitcoms:** every sitcom ever (thousands, infinite scroll), greatest sitcoms, the 60s to the 2020s, animated, British, mockumentary, workplace, dark comedy
- **India:** trending in Malayalam/Tamil/Hindi/Telugu, every Malayalam/Tamil/Hindi movie, masterpieces, thrillers, comedy, Mollywood golden era, Malayalam & Tamil series, best Indian series, star collections (Mohanlal, Mammootty, Fahadh, Prithviraj, Dulquer, Rajinikanth, Vijay, Kamal Haasan)
- **Unlimited:** every movie (10,000), top 5,000 rated, every series (6,000), plus 30+ genre/theme shelves
- **18+:** every R-rated movie, NC-17, erotic thrillers, steamy & explicit movies/series, gore, ultra-violent, drugs, disturbing, Indian A-rated, After Dark series (mainstream rated titles only)
- **Anime:** most popular, masterpieces, airing now, anime movies, shōnen, isekai, mecha, seinen, Studio Ghibli
- **Platform originals:** Netflix, HBO, Max, Prime Video, Apple TV+, Disney+, Hulu, FX, AMC, BBC, Adult Swim
- **Moods and themes:** binge-worthy, hidden gems, miniseries, true crime, K-drama, time travel, end of the world, heists, mind-bending twists, cyberpunk, cult classics, under 90 minutes, and more
- **Personal:** My Favourites, For You (built from TMDB recommendations of your favourites), Because You Like…, After Dark 18+

Each title shows a ★ rating, the year and the reason it was recommended.

## One-time setup
1. Repo → Settings → Secrets and variables → Actions → **New repository secret**
   Name: `TMDB_API_KEY`, value: your TMDB v3 API key *or* v4 read access token
2. Actions tab → **Rebuild collections** → **Run workflow** (the first run takes 5–15 minutes)

## Customise
Edit `tools/build_tmdb.py`:
- `FAV_SERIES` / `FAV_MOVIES`: your taste. Add `Title:Year` when a name is ambiguous.
- `AFTER_DARK`: picks for the 18+ shelf
- `CATALOGS`: add, remove or resize shelves (one line each)
- `STYLE = "plain"` if your TV shows boxes instead of the 𝗳𝗮𝗻𝗰𝘆 shelf names

Push the change and the Action rebuilds automatically.
Test without a key: `python tools/build_tmdb.py --selftest`
