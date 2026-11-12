# Sayand's Collections: Nuvio / Stremio add-on

Install in Nuvio → Add-ons → Install from URL:

```
https://sayandp.github.io/nuvio-collections/manifest.json
```

Five catalogs, each with a subcategory filter. Rebuilt daily from TMDB by a GitHub Action.

| Catalog | Subcategories |
|---|---|
| 😂 Sitcoms | Trending Now, All Sitcoms, Top Rated, Latest, 60s, 70s, 80s, 90s, 2000s, 2010s, 2020s, Animated, British, Mockumentary, Workplace, Family |
| 🌴 Malayalam Movies | Trending Now, Latest Releases, All Movies, Top Rated, This Year, Thriller, Comedy, Family Drama, Action and Mass, Romance, Horror, 80s and 90s Classics, Mohanlal, Mammootty, Fahadh Faasil, Prithviraj, Dulquer Salmaan |
| 🎺 Tamil Movies | Trending Now, Latest Releases, All Movies, Top Rated, This Year, Action and Mass, Thriller, Comedy, Romance, Family Drama, Horror, 80s and 90s Classics, Rajinikanth, Vijay, Kamal Haasan, Suriya, Dhanush |
| 🔞 18+ Movies | Trending 18+, All 18+ Movies, Latest 18+, Top Rated 18+, NC-17 and Uncut, Steamy and Explicit, Erotic Thrillers, Ultra-Violent, Gore and Extreme Horror, Crime and Gangster, Drugs and Excess, Disturbing and Dark, Indian A-Rated |
| 🔞 18+ Series | Trending 18+, All 18+ Series, Latest 18+, Top Rated 18+, Steamy and Explicit, Brutal and Violent, Crime and Gangster, Fantasy and War Epics, Dark Comedy, Drugs and Excess |

"All …" lists go up to 10,000 titles (TMDB's limit) and load 100 at a time as you scroll.
18+ means mainstream R / NC-17 / TV-MA / A-rated titles. TMDB's adult category is excluded.

Edit `GROUPS` in `tools/build_tmdb.py` to change subcategories. Pushing the change rebuilds automatically.
Test without a key: `python tools/build_tmdb.py --selftest`
