#!/usr/bin/env python3
"""
Sayand's Collections — TMDB-powered Nuvio / Stremio catalog add-on (static, rebuilt daily).

    TMDB_API_KEY=xxxx python tools/build_tmdb.py          # real build (v3 key or v4 read token)
    python tools/build_tmdb.py --selftest                 # offline test with fake TMDB data

Writes manifest.json + catalog/ at the repo root (served by GitHub Pages).
Edit CONFIG below: favourites, after-dark picks, page limits, name style.
"""
import concurrent.futures as cf
import datetime as dt
import json, os, random, re, shutil, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "imdb_cache.json")
VERSION = "2.0." + dt.date.today().strftime("%Y%m%d")
PAGE = 100                       # metas per static page (Nuvio asks with ?skip=)
TODAY = dt.date.today()

# ============================================================================
# CONFIG
# ============================================================================
STYLE = "bold"                   # "bold" (𝗙𝗮𝗻𝗰𝘆 letters) | "plain" (if your TV shows boxes)

FAV_SERIES = ["Breaking Bad", "Game of Thrones", "Friends", "The Office:2005", "Dark",
              "Peaky Blinders", "Money Heist", "Sherlock", "Chernobyl", "Stranger Things",
              "Better Call Saul", "The Boys", "Brooklyn Nine-Nine", "Seinfeld"]
FAV_MOVIES = ["Interstellar", "Inception", "The Dark Knight", "Parasite", "The Shawshank Redemption",
              "Whiplash", "Joker:2019", "Fight Club", "Spirited Away", "The Prestige"]
BECAUSE_SERIES = 5               # "Because you like …" shelves from the first N favourites
BECAUSE_MOVIES = 3

AFTER_DARK = ["Game of Thrones", "House of the Dragon", "Spartacus", "The Boys", "Euphoria",
              "Westworld", "Rome", "Boardwalk Empire", "The Sopranos", "Peaky Blinders", "Vikings",
              "The Witcher", "Gen V", "Banshee", "Outlander", "Shōgun", "Deadwood", "True Blood",
              "The Deuce", "Hannibal", "Dexter", "Narcos", "Squid Game", "Kingdom:2019", "Ozark",
              "The Last of Us", "Fargo", "Mindhunter", "Sacred Games", "Mirzapur", "Invincible",
              "Fallout", "Black Mirror", "Babylon Berlin", "Penny Dreadful", "Preacher", "Oz",
              "Hap and Leonard", "The Terror", "Utopia:2013"]

# Each catalog: id, type (series|movie), title, emoji, source, params, max items.
#   src "trending:<window>" | "list:<path>" | "discover"  (+ kw = keyword names, resolved live)
T, Mv = "series", "movie"
SINCE = lambda days: (TODAY - dt.timedelta(days=days)).isoformat()
def dec(a, b, field="first_air_date"):
    return {f"{field}.gte": f"{a}-01-01", f"{field}.lte": f"{b}-12-31"}
POP = {"sort_by": "popularity.desc"}
TOP = {"sort_by": "vote_average.desc", "vote_count.gte": 300}

CATALOGS = [
  # ---------------- trending & charts
  ("trending-series-day",  T,  "Trending Today · Series",   "🔥", "trending:day",  {}, 100),
  ("trending-movies-day",  Mv, "Trending Today · Movies",   "🔥", "trending:day",  {}, 100),
  ("trending-series-week", T,  "Trending This Week · Series","📈", "trending:week", {}, 200),
  ("trending-movies-week", Mv, "Trending This Week · Movies","📈", "trending:week", {}, 200),
  ("popular-series",       T,  "Most Popular Series",       "⭐", "list:tv/popular", {}, 300),
  ("popular-movies",       Mv, "Most Popular Movies",       "⭐", "list:movie/popular", {}, 300),
  ("top-rated-series",     T,  "All-Time Top Rated Series", "🏆", "list:tv/top_rated", {}, 500),
  ("top-rated-movies",     Mv, "All-Time Top Rated Movies", "🏆", "list:movie/top_rated", {}, 500),
  ("now-playing",          Mv, "Fresh From Theatres",       "🎟️", "list:movie/now_playing", {}, 100),
  ("airing-this-week",     T,  "New Episodes This Week",    "📺", "list:tv/on_the_air", {}, 200),

  # ---------------- sitcoms  (thousands, paginated)
  ("sitcoms-all",       T, "Every Sitcom Ever",          "😂", "discover", {**POP}, 4000, ["sitcom"]),
  ("sitcoms-top",       T, "Greatest Sitcoms",           "👑", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 150}, 500, ["sitcom"]),
  ("sitcoms-60s",       T, "Sitcoms · The 60s",          "📻", "discover", {**POP, **dec(1950, 1969)}, 400, ["sitcom"]),
  ("sitcoms-70s",       T, "Sitcoms · The 70s",          "🕺", "discover", {**POP, **dec(1970, 1979)}, 500, ["sitcom"]),
  ("sitcoms-80s",       T, "Sitcoms · The 80s",          "📼", "discover", {**POP, **dec(1980, 1989)}, 500, ["sitcom"]),
  ("sitcoms-90s",       T, "Sitcoms · The 90s",          "☕", "discover", {**POP, **dec(1990, 1999)}, 600, ["sitcom"]),
  ("sitcoms-00s",       T, "Sitcoms · The 2000s",        "📀", "discover", {**POP, **dec(2000, 2009)}, 800, ["sitcom"]),
  ("sitcoms-10s",       T, "Sitcoms · The 2010s",        "📱", "discover", {**POP, **dec(2010, 2019)}, 800, ["sitcom"]),
  ("sitcoms-20s",       T, "Sitcoms · The 2020s",        "✨", "discover", {**POP, **dec(2020, TODAY.year)}, 600, ["sitcom"]),
  ("sitcoms-animated",  T, "Animated Sitcoms",           "🍩", "discover", {**POP, "with_genres": "16,35"}, 500),
  ("mockumentary",      T, "Mockumentary Comedies",      "🎥", "discover", {**POP}, 200, ["mockumentary"]),
  ("workplace-comedy",  T, "Workplace Comedies",         "💼", "discover", {**POP}, 300, ["workplace comedy"]),
  ("british-sitcoms",   T, "British Sitcoms",            "☂️", "discover", {**POP, "with_origin_country": "GB"}, 400, ["sitcom"]),
  ("dark-comedy-tv",    T, "Dark Comedy Series",         "🖤", "discover", {**POP}, 300, ["dark comedy"]),

  # ---------------- anime
  ("anime-popular",     T,  "Anime · Most Popular",      "🌸", "discover", {**POP, "with_genres": "16", "with_original_language": "ja"}, 1000),
  ("anime-top",         T,  "Anime · Masterpieces",      "🏯", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 200, "with_genres": "16", "with_original_language": "ja"}, 400),
  ("anime-airing",      T,  "Anime · Airing Now",        "📡", "discover", {**POP, "with_genres": "16", "with_original_language": "ja", "air_date.gte": SINCE(30)}, 200),
  ("anime-movies",      Mv, "Anime Movies",              "🎐", "discover", {**POP, "with_genres": "16", "with_original_language": "ja"}, 500),
  ("anime-shounen",     T,  "Shōnen Battles",            "⚔️", "discover", {**POP, "with_genres": "16"}, 300, ["shounen"]),
  ("anime-isekai",      T,  "Isekai Worlds",             "🌀", "discover", {**POP, "with_genres": "16"}, 300, ["isekai"]),
  ("anime-mecha",       T,  "Mecha & Giant Robots",      "🤖", "discover", {**POP, "with_genres": "16"}, 200, ["mecha"]),
  ("anime-seinen",      T,  "Seinen · Darker Anime",     "🌑", "discover", {**POP, "with_genres": "16"}, 200, ["seinen"]),
  ("ghibli",            Mv, "Studio Ghibli",             "🍃", "discover", {**POP, "with_companies": "10342"}, 60),

  # ---------------- platform originals
  ("netflix",   T, "Netflix Originals",     "🟥", "discover", {**POP, "with_networks": "213"}, 600),
  ("hbo",       T, "HBO Originals",         "⬛", "discover", {**POP, "with_networks": "49"}, 400),
  ("max",       T, "Max Originals",         "🟦", "discover", {**POP, "with_networks": "3186"}, 200),
  ("prime",     T, "Prime Video Originals", "🔷", "discover", {**POP, "with_networks": "1024"}, 400),
  ("apple",     T, "Apple TV+ Originals",   "🍎", "discover", {**POP, "with_networks": "2552"}, 200),
  ("disney",    T, "Disney+ Originals",     "🏰", "discover", {**POP, "with_networks": "2739"}, 200),
  ("hulu",      T, "Hulu Originals",        "🟩", "discover", {**POP, "with_networks": "453"}, 200),
  ("fx",        T, "FX Originals",          "🎬", "discover", {**POP, "with_networks": "88"}, 200),
  ("amc",       T, "AMC Originals",         "🧟", "discover", {**POP, "with_networks": "174"}, 200),
  ("bbc",       T, "BBC Originals",         "🇬🇧", "discover", {**POP, "with_networks": "4"}, 300),
  ("adult-swim",T, "Adult Swim",            "🌊", "discover", {**POP, "with_networks": "80"}, 200),

  # ---------------- series moods & genres
  ("binge-worthy",     T, "Binge-Worthy · 8+ Rated",   "🍿", "discover", {"sort_by": "popularity.desc", "vote_average.gte": 8, "vote_count.gte": 800}, 300),
  ("hidden-gem-series",T, "Hidden Gem Series",         "💎", "discover", {"sort_by": "vote_average.desc", "vote_average.gte": 7.8, "vote_count.gte": 80, "vote_count.lte": 700}, 300),
  ("miniseries",       T, "Perfect Miniseries",        "🧩", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 150, "with_type": "2"}, 300),
  ("crime-series",     T, "Crime & Gangster Series",   "🔫", "discover", {**POP, "with_genres": "80"}, 600),
  ("scifi-fantasy-tv", T, "Sci-Fi & Fantasy Series",   "🚀", "discover", {**POP, "with_genres": "10765"}, 600),
  ("mystery-series",   T, "Mystery & Whodunits",       "🕵️", "discover", {**POP, "with_genres": "9648"}, 400),
  ("war-politics-tv",  T, "War & Politics",            "🎖️", "discover", {**POP, "with_genres": "10768"}, 300),
  ("docuseries",       T, "Docuseries",                "🎙️", "discover", {**POP, "with_genres": "99"}, 300),
  ("true-crime-tv",    T, "True Crime",                "🩸", "discover", {**POP}, 300, ["true crime"]),
  ("k-drama",          T, "K-Drama Hits",              "💜", "discover", {**POP, "with_original_language": "ko", "with_genres": "18"}, 400),
  ("superhero-tv",     T, "Superhero Series",          "🦸", "discover", {**POP}, 200, ["superhero"]),
  ("post-apoc-tv",     T, "End of the World",          "☢️", "discover", {**POP}, 200, ["post-apocalyptic future"]),
  ("time-travel-tv",   T, "Time-Travel Series",        "⏳", "discover", {**POP}, 200, ["time travel"]),
  ("adult-animation",  T, "Adult Animation",           "🧪", "discover", {**POP}, 300, ["adult animation"]),
  ("teen-drama",       T, "Teen Drama",                "🎒", "discover", {**POP}, 300, ["teen drama"]),
  ("medical-drama",    T, "Medical Drama",             "🩺", "discover", {**POP}, 200, ["medical drama"]),
  ("legal-drama",      T, "Legal Drama",               "⚖️", "discover", {**POP}, 200, ["legal drama"]),

  # ---------------- movie collections
  ("mind-bending",     Mv, "Mind-Bending Twists",      "🧠", "discover", {**POP}, 300, ["twist ending"]),
  ("time-travel-mov",  Mv, "Time-Travel Movies",       "⏳", "discover", {**POP}, 200, ["time travel"]),
  ("heist",            Mv, "Heists & Capers",          "💰", "discover", {**POP}, 200, ["heist"]),
  ("serial-killer",    Mv, "Serial-Killer Thrillers",  "🔪", "discover", {**POP}, 200, ["serial killer"]),
  ("true-story",       Mv, "Based on a True Story",    "📰", "discover", {**POP}, 300, ["based on true story"]),
  ("dystopia",         Mv, "Dystopian Futures",        "🏙️", "discover", {**POP}, 200, ["dystopia"]),
  ("cyberpunk",        Mv, "Cyberpunk",                "🌃", "discover", {**POP}, 150, ["cyberpunk"]),
  ("space",            Mv, "Lost in Space",            "🪐", "discover", {**POP}, 200, ["space travel"]),
  ("zombies",          Mv, "Zombies",                  "🧟", "discover", {**POP}, 200, ["zombie"]),
  ("superhero-mov",    Mv, "Superhero Movies",         "🦸", "discover", {**POP}, 300, ["superhero"]),
  ("coming-of-age",    Mv, "Coming of Age",            "🌅", "discover", {**POP}, 300, ["coming of age"]),
  ("cult-classics",    Mv, "Cult Classics",            "🦇", "discover", {**POP}, 200, ["cult film"]),
  ("martial-arts",     Mv, "Martial Arts",             "🥋", "discover", {**POP}, 200, ["martial arts"]),
  ("psych-thriller",   Mv, "Psychological Thrillers",  "🌀", "discover", {**POP}, 300, ["psychological thriller"]),
  ("revenge",          Mv, "Revenge Stories",          "🗡️", "discover", {**POP}, 200, ["revenge"]),
  ("feel-good",        Mv, "Feel-Good Movies",         "🌈", "discover", {**POP}, 200, ["feel-good"]),
  ("hidden-gem-movies",Mv, "Hidden Gem Movies",        "💎", "discover", {"sort_by": "vote_average.desc", "vote_average.gte": 7.4, "vote_count.gte": 200, "vote_count.lte": 2000}, 300),
  ("quick-watch",      Mv, "Under 90 Minutes",         "⏱️", "discover", {**POP, "with_runtime.lte": 90, "with_runtime.gte": 60, "vote_average.gte": 6.5, "vote_count.gte": 300}, 300),
  ("action",           Mv, "Pure Action",              "💥", "discover", {**POP, "with_genres": "28"}, 500),
  ("horror",           Mv, "Horror Night",             "👻", "discover", {**POP, "with_genres": "27"}, 500),
  ("scifi-movies",     Mv, "Sci-Fi Movies",            "🛸", "discover", {**POP, "with_genres": "878"}, 500),
  ("romance",          Mv, "Date Night Romance",       "💘", "discover", {**POP, "with_genres": "10749"}, 300),
  ("comedy-movies",    Mv, "Comedy Movies",            "🤣", "discover", {**POP, "with_genres": "35"}, 500),
  ("family-animation", Mv, "Animated Family Movies",   "🧸", "discover", {**POP, "with_genres": "16,10751"}, 300),
  ("documentaries",    Mv, "Documentaries",            "🌍", "discover", {**POP, "with_genres": "99"}, 300),
  ("movies-80s",       Mv, "Best of the 80s",          "📼", "discover", {**TOP, **dec(1980, 1989, "primary_release_date")}, 300),
  ("movies-90s",       Mv, "Best of the 90s",          "💿", "discover", {**TOP, **dec(1990, 1999, "primary_release_date")}, 300),
  ("movies-00s",       Mv, "Best of the 2000s",        "📀", "discover", {**TOP, **dec(2000, 2009, "primary_release_date")}, 300),
  ("after-dark-movies",Mv, "After Dark · R-Rated Hits","🔞", "discover", {**POP, "certification_country": "US", "certification": "R|NC-17", "vote_count.gte": 500}, 300),
]

# ============================================================================
# TMDB client
# ============================================================================
KEY = os.environ.get("TMDB_API_KEY", "").strip()
API = "https://api.themoviedb.org/3/"
IMG = "https://image.tmdb.org/t/p/"

def _get_real(path, params=None):
    params = dict(params or {})
    headers = {"Accept": "application/json", "User-Agent": "sayand-nuvio-collections"}
    if KEY.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + KEY
    else:
        params["api_key"] = KEY
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(1.5 * (attempt + 1)); continue
            if e.code == 404:
                return {}
            raise
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}

get = _get_real
tt = lambda typ: "tv" if typ == T else "movie"

def paged(path, params, maxn):
    out, page = [], 1
    while len(out) < maxn and page <= 500:
        d = get(path, {**params, "page": page})
        res = d.get("results") or []
        out += res
        if page >= (d.get("total_pages") or 1) or not res:
            break
        page += 1
    return out[:maxn]

KW = {}
def keyword_id(name):
    if name not in KW:
        res = get("search/keyword", {"query": name}).get("results") or []
        exact = [k for k in res if k["name"].lower() == name.lower()]
        KW[name] = str((exact or res or [{"id": None}])[0]["id"] or "")
    return KW[name]

def search(title, typ):
    name, _, year = title.partition(":")
    p = {"query": name}
    if year:
        p["first_air_date_year" if typ == T else "year"] = year
    res = get(f"search/{tt(typ)}", p).get("results") or []
    res.sort(key=lambda r: -(r.get("vote_count") or 0))
    return res[0] if res else None

# ---- IMDb id mapping (cached in data/imdb_cache.json, only new titles are fetched)
CACHE_D = {}
def load_cache():
    global CACHE_D
    try:
        CACHE_D = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        CACHE_D = {}

def imdb_ids(items):
    need = sorted({k for k in items if k not in CACHE_D})
    def one(k):
        typ, tid = k.split(":")
        d = get(f"{typ}/{tid}/external_ids")
        return k, d.get("imdb_id") or ""
    with cf.ThreadPoolExecutor(12) as ex:
        for k, v in ex.map(one, need):
            CACHE_D[k] = v
    if need:
        print(f"  mapped {len(need)} new titles to IMDb ids")

# ============================================================================
# Building
# ============================================================================
BOLD = {**{chr(ord('A') + i): chr(0x1D5D4 + i) for i in range(26)},
        **{chr(ord('a') + i): chr(0x1D5EE + i) for i in range(26)},
        **{chr(ord('0') + i): chr(0x1D7EC + i) for i in range(10)}}
def fancy(title, emoji):
    if STYLE == "bold":
        title = "".join(BOLD.get(c, c) for c in title)
    return f"{emoji}  {title}"

GENRES = {}
def load_genres():
    for typ in ("tv", "movie"):
        for g in get(f"genre/{typ}/list").get("genres", []):
            GENRES[g["id"]] = g["name"]

def year_of(r):
    d = r.get("first_air_date") or r.get("release_date") or ""
    return d[:4]

def to_meta(r, typ, reason=None):
    k = f"{tt(typ)}:{r['id']}"
    iid = CACHE_D.get(k)
    if not iid:
        return None
    rating = r.get("vote_average") or 0
    yr = year_of(r)
    bits = [f"★ {rating:.1f}" if rating else None, yr or None, reason]
    head = " · ".join(b for b in bits if b)
    ov = (r.get("overview") or "").strip()
    if len(ov) > 220:
        ov = ov[:217].rsplit(" ", 1)[0] + "…"
    m = {"id": iid, "type": typ, "name": r.get("name") or r.get("title"),
         "posterShape": "poster", "releaseInfo": yr,
         "description": (head + ("\n" + ov if ov else "")).strip(),
         "genres": [GENRES[g] for g in (r.get("genre_ids") or []) if g in GENRES][:3]}
    if rating:
        m["imdbRating"] = f"{rating:.1f}"
    if r.get("poster_path"):
        m["poster"] = IMG + "w500" + r["poster_path"]
    if r.get("backdrop_path"):
        m["background"] = IMG + "w1280" + r["backdrop_path"]
    return m

def fetch_catalog(c):
    cid, typ, title, emoji, src, params, maxn = c[:7]
    kws = c[7] if len(c) > 7 else []
    p = dict(params)
    if kws:
        ids = [keyword_id(k) for k in kws]
        ids = [i for i in ids if i]
        if not ids:
            print(f"  skip {cid}: keyword not on TMDB {kws}")
            return []
        p["with_keywords"] = "|".join(ids)
    if src.startswith("trending:"):
        return paged(f"trending/{tt(typ)}/{src.split(':')[1]}", {}, maxn)
    if src.startswith("list:"):
        return paged(src.split(":", 1)[1], {}, maxn)
    p.setdefault("include_adult", "false")
    return paged(f"discover/{tt(typ)}", p, maxn)

def recommend(favs, typ):
    """For You = TMDB recommendations of every favourite, scored by rank and agreement."""
    found = [(f, search(f, typ)) for f in favs]
    found = [(f.split(":")[0], r) for f, r in found if r]
    score, why, per_fav = {}, {}, {}
    fav_ids = {r["id"] for _, r in found}
    for fname, r in found:
        recs = paged(f"{tt(typ)}/{r['id']}/recommendations", {}, 40)
        recs = [x for x in recs if x["id"] not in fav_ids]
        per_fav[fname] = recs
        for rank, x in enumerate(recs):
            w = 1.0 / (1 + rank * 0.15) * (0.5 + (x.get("vote_average") or 0) / 20)
            if x["id"] not in score or w > why[x["id"]][1]:
                why[x["id"]] = (fname, w)
            score[x["id"]] = score.get(x["id"], 0) + w
            score.setdefault(("obj", x["id"]), x)
    ranked = sorted((k for k in score if not isinstance(k, tuple)), key=lambda k: -score[k])
    top = max((score[k] for k in ranked), default=1)
    items = [(score[("obj", k)], f"{int(100 * score[k] / top)}% match · because you like {why[k][0]}") for k in ranked[:200]]
    return [r for _, r in found], items, per_fav

def write_catalog(cid, typ, metas, catalogs, name):
    if not metas:
        return
    base = os.path.join(ROOT, "catalog", typ)
    os.makedirs(os.path.join(base, cid), exist_ok=True)
    for i in range(0, len(metas), PAGE):
        chunk = {"metas": metas[i:i + PAGE]}
        path = os.path.join(base, f"{cid}.json") if i == 0 else os.path.join(base, cid, f"skip={i}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, separators=(",", ":"))
    # empty page after the last one so infinite scroll stops cleanly
    with open(os.path.join(base, cid, f"skip={((len(metas) - 1) // PAGE + 1) * PAGE}.json"), "w") as f:
        f.write('{"metas":[]}')
    catalogs.append({"type": typ, "id": cid, "name": name, "extra": [{"name": "skip", "isRequired": False}]})

def build():
    if not KEY and get is _get_real:
        sys.exit("Set TMDB_API_KEY (repo secret) — see README.")
    t0 = time.time()
    load_cache(); load_genres()
    raw = {}       # cid -> [(tmdb_result, reason)]
    order = []     # (cid, typ, display name)

    # personal shelves first
    for typ, favs, label, nb in ((T, FAV_SERIES, "Series", BECAUSE_SERIES), (Mv, FAV_MOVIES, "Movies", BECAUSE_MOVIES)):
        fav_objs, recs, per_fav = recommend(favs, typ)
        sfx = "series" if typ == T else "movies"
        raw[f"fav-{sfx}"] = [(r, "one of your favourites") for r in fav_objs]
        order.append((f"fav-{sfx}", typ, fancy(f"My Favourite {label}", "❤️")))
        raw[f"for-you-{sfx}"] = recs
        order.append((f"for-you-{sfx}", typ, fancy(f"For You · {label}", "🎯")))
        for fname in list(per_fav)[:nb]:
            slug = re.sub(r"[^a-z0-9]+", "-", fname.lower()).strip("-")
            raw[f"because-{slug}"] = [(r, f"because you like {fname}") for r in per_fav[fname]]
            order.append((f"because-{slug}", typ, fancy(f"Because You Like {fname}", "💡")))
    ad = [search(t, T) for t in AFTER_DARK]
    raw["after-dark-series"] = [(r, "18+ · mature themes") for r in ad if r]
    after_dark_pos = len(order)

    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(fetch_catalog, c): c for c in CATALOGS}
        res = {futs[f][0]: f.result() for f in cf.as_completed(futs)}
    for c in CATALOGS:
        cid, typ, title, emoji = c[:4]
        raw[cid] = [(r, None) for r in res.get(cid, [])]
        order.append((cid, typ, fancy(title, emoji)))
        if cid == "airing-this-week":
            order.append(("after-dark-series", T, fancy("After Dark · 18+ Series", "🔞")))

    typ_of = {cid: typ for cid, typ, _ in order}
    imdb_ids({f"{tt(typ_of[cid])}:{r['id']}" for cid, items in raw.items() for r, _ in items})

    shutil.rmtree(os.path.join(ROOT, "catalog"), ignore_errors=True)
    catalogs, total, uniq = [], 0, set()
    for cid, typ, name in order:
        metas, seen = [], set()
        for r, why in raw.get(cid, []):
            m = to_meta(r, typ, why)
            if m and m["id"] not in seen:
                seen.add(m["id"]); metas.append(m)
        write_catalog(cid, typ, metas, catalogs, name)
        total += len(metas); uniq |= seen
        print(f"  {len(metas):5d}  {cid}")

    manifest = {
        "id": "com.sayand.nuvio.collections",
        "version": VERSION,
        "name": "Sayand's Collections",
        "description": f"{len(catalogs)} hand-picked shelves rebuilt daily from TMDB: trending, every sitcom ever by era, "
                       "anime, platform originals, moods, ratings and a taste-based recommender.",
        "logo": "https://www.themoviedb.org/assets/2/v4/logos/v2/blue_square_2-d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b.svg",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "catalogs": catalogs,
        "behaviorHints": {"configurable": False, "adult": False},
    }
    with open(os.path.join(ROOT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(CACHE_D, f, separators=(",", ":"), sort_keys=True)
    print(f"built {len(catalogs)} catalogs · {total} entries · {len(uniq)} unique titles · {time.time() - t0:.0f}s")

# ============================================================================
# Offline self-test (fake TMDB) — checks paging, mapping, recommender, files
# ============================================================================
def _fake_get(path, params=None):
    params = params or {}
    rnd = random.Random(path + json.dumps(params, sort_keys=True))
    if path.startswith("genre/"):
        return {"genres": [{"id": 35, "name": "Comedy"}, {"id": 18, "name": "Drama"}, {"id": 16, "name": "Animation"}]}
    if path == "search/keyword":
        return {"results": [] if params["query"] == "feel-good" else [{"id": abs(hash(params["query"])) % 99999, "name": params["query"]}]}
    if path.endswith("external_ids"):
        tid = int(path.split("/")[1])
        return {"imdb_id": "" if tid % 17 == 0 else f"tt{tid:07d}"}
    page = int(params.get("page", 1))
    total_pages = 3 if "keyword" in json.dumps(params) or path.startswith("search") else 40
    results = [{"id": rnd.randint(1, 900000), "name": f"Show {rnd.randint(1, 9999)}", "title": f"Film {rnd.randint(1, 9999)}",
                "vote_average": round(rnd.uniform(5, 9.3), 1), "vote_count": rnd.randint(10, 9000),
                "first_air_date": f"{rnd.randint(1965, 2026)}-05-01", "release_date": f"{rnd.randint(1965, 2026)}-05-01",
                "genre_ids": [35, 18], "overview": "A test overview " * 20, "poster_path": "/p.jpg", "backdrop_path": "/b.jpg"}
               for _ in range(20)]
    return {"results": results, "page": page, "total_pages": total_pages}

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        get = _fake_get
        ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest")
        CACHE = os.path.join(ROOT, "data", "imdb_cache.json")
        shutil.rmtree(ROOT, ignore_errors=True)
    build()
