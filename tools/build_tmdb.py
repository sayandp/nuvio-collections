#!/usr/bin/env python3
"""
Sayand's Collections v4 — 5 clean catalogs, each with a subcategory (genre) filter.

    TMDB_API_KEY=xxxx python tools/build_tmdb.py      # real build (v3 key or v4 read token)
    python tools/build_tmdb.py --selftest             # offline test with fake TMDB data

In Nuvio each catalog shows as ONE row on Home (its first subcategory).
Open the catalog / Discover to switch subcategory with the filter.
Edit GROUPS below to add / remove subcategories.
"""
import concurrent.futures as cf
import datetime as dt
import json, os, random, shutil, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "imdb_cache.json")
VERSION = "4.0." + dt.date.today().strftime("%Y%m%d")
INCLUDE_LEGACY = True          # False = only the top 5 catalogs
PAGE = 100                     # metas per static page; Nuvio loads more with ?skip=
MAX = 10000                    # TMDB's hard ceiling per list (500 pages x 20)
TODAY = dt.date.today()

T, Mv = "series", "movie"
SINCE = lambda days: (TODAY - dt.timedelta(days=days)).isoformat()
NOW = TODAY.isoformat()
def dec(a, b, field):
    return {f"{field}.gte": f"{a}-01-01", f"{field}.lte": f"{b}-12-31"}
POP = {"sort_by": "popularity.desc"}
RATED = lambda n: {"sort_by": "vote_average.desc", "vote_count.gte": n}
LATEST_M = {"sort_by": "primary_release_date.desc", "primary_release_date.lte": NOW}
LATEST_T = {"sort_by": "first_air_date.desc", "first_air_date.lte": NOW}

# ============================================================================
# GROUPS:  (catalog id, type, name, base params, base keywords, [subcategories])
#   subcategory: (label, extra params, max items, extra keywords)
#   "_cast": "Actor Name" in params -> filmography of that actor
# ============================================================================
SITCOM_KW = ["sitcom", "british sitcom", "family sitcom", "workplace comedy", "mockumentary", "multi-camera"]
ML = {"with_original_language": "ml"}
TA = {"with_original_language": "ta"}
R_MOV = {"certification_country": "US", "certification": "R|NC-17"}
MA_TV = {"certification_country": "US", "certification": "TV-MA"}
MA_TV_FALLBACK_KW = ["violence", "graphic violence", "nudity", "sex scene", "drug use", "strong language"]

GROUPS = [
 ("sitcoms", T, "😂  Sitcoms", {}, SITCOM_KW, [
    ("Trending Now",    {**POP, "air_date.gte": SINCE(365)}, 500, None),
    ("All Sitcoms",     {**POP}, MAX, None),
    ("Top Rated",       RATED(150), 1000, None),
    ("Latest",          {**LATEST_T, "vote_count.gte": 5}, 500, None),
    ("60s",             {**POP, **dec(1950, 1969, "first_air_date")}, 1000, None),
    ("70s",             {**POP, **dec(1970, 1979, "first_air_date")}, 1000, None),
    ("80s",             {**POP, **dec(1980, 1989, "first_air_date")}, 1000, None),
    ("90s",             {**POP, **dec(1990, 1999, "first_air_date")}, 1500, None),
    ("2000s",           {**POP, **dec(2000, 2009, "first_air_date")}, 2000, None),
    ("2010s",           {**POP, **dec(2010, 2019, "first_air_date")}, 2000, None),
    ("2020s",           {**POP, **dec(2020, TODAY.year, "first_air_date")}, 1500, None),
    ("Animated",        {**POP, "with_genres": "16"}, 1000, None),
    ("British",         {**POP, "with_origin_country": "GB"}, 1000, None),
    ("Mockumentary",    {**POP}, 300, ["mockumentary"]),
    ("Workplace",       {**POP}, 500, ["workplace comedy"]),
    ("Family",          {**POP, "with_genres": "10751"}, 1000, None),
 ]),
 ("malayalam", Mv, "🌴  Malayalam Movies", ML, None, [
    ("Trending Now",    {**POP, "primary_release_date.gte": SINCE(150)}, 300, None),
    ("Latest Releases", {**LATEST_M}, 500, None),
    ("All Movies",      {**POP}, MAX, None),
    ("Top Rated",       RATED(30), 1000, None),
    ("This Year",       {**POP, "primary_release_date.gte": f"{TODAY.year}-01-01"}, 500, None),
    ("Thriller",        {**POP, "with_genres": "53|9648"}, 2000, None),
    ("Comedy",          {**POP, "with_genres": "35"}, 2000, None),
    ("Family Drama",    {**POP, "with_genres": "10751|18"}, 3000, None),
    ("Action & Mass",   {**POP, "with_genres": "28|80"}, 2000, None),
    ("Romance",         {**POP, "with_genres": "10749"}, 1500, None),
    ("Horror",          {**POP, "with_genres": "27"}, 500, None),
    ("80s & 90s Classics", {**RATED(5), **dec(1980, 1999, "primary_release_date")}, 1500, None),
    ("Mohanlal",        {**POP, "_cast": "Mohanlal"}, 500, None),
    ("Mammootty",       {**POP, "_cast": "Mammootty"}, 500, None),
    ("Fahadh Faasil",   {**POP, "_cast": "Fahadh Faasil"}, 200, None),
    ("Prithviraj",      {**POP, "_cast": "Prithviraj Sukumaran"}, 200, None),
    ("Dulquer Salmaan", {**POP, "_cast": "Dulquer Salmaan"}, 150, None),
 ]),
 ("tamil", Mv, "🎺  Tamil Movies", TA, None, [
    ("Trending Now",    {**POP, "primary_release_date.gte": SINCE(150)}, 300, None),
    ("Latest Releases", {**LATEST_M}, 500, None),
    ("All Movies",      {**POP}, MAX, None),
    ("Top Rated",       RATED(30), 1000, None),
    ("This Year",       {**POP, "primary_release_date.gte": f"{TODAY.year}-01-01"}, 500, None),
    ("Action & Mass",   {**POP, "with_genres": "28|80"}, 3000, None),
    ("Thriller",        {**POP, "with_genres": "53|9648"}, 2000, None),
    ("Comedy",          {**POP, "with_genres": "35"}, 2000, None),
    ("Romance",         {**POP, "with_genres": "10749"}, 2000, None),
    ("Family Drama",    {**POP, "with_genres": "10751|18"}, 3000, None),
    ("Horror",          {**POP, "with_genres": "27"}, 500, None),
    ("80s & 90s Classics", {**RATED(5), **dec(1980, 1999, "primary_release_date")}, 1500, None),
    ("Rajinikanth",     {**POP, "_cast": "Rajinikanth"}, 250, None),
    ("Vijay",           {**POP, "_cast": "Vijay:Joseph Vijay"}, 150, None),
    ("Kamal Haasan",    {**POP, "_cast": "Kamal Haasan"}, 300, None),
    ("Suriya",          {**POP, "_cast": "Suriya"}, 100, None),
    ("Dhanush",         {**POP, "_cast": "Dhanush"}, 100, None),
 ]),
 ("adult-movies", Mv, "🔞  18+ Movies", {}, None, [
    ("Trending 18+",        {**POP, **R_MOV, "primary_release_date.gte": SINCE(365)}, 500, None),
    ("All 18+ Movies",      {**POP, **R_MOV}, MAX, None),
    ("Latest 18+",          {**LATEST_M, **R_MOV, "vote_count.gte": 10}, 500, None),
    ("Top Rated 18+",       {**RATED(500), **R_MOV}, 2000, None),
    ("NC-17 & Uncut",       {**POP, "certification_country": "US", "certification": "NC-17"}, 1000, None),
    ("Steamy & Explicit",   {**POP}, 3000, ["nudity", "sex scene", "female nudity", "erotic movie"]),
    ("Erotic Thrillers",    {**POP}, 1000, ["erotic thriller", "sensuality"]),
    ("Ultra-Violent",       {**POP, "vote_count.gte": 50}, 3000, ["violence", "brutality", "extreme violence", "bloodbath"]),
    ("Gore & Extreme Horror", {**POP}, 2000, ["gore", "splatter", "body horror", "torture"]),
    ("Crime & Gangster",    {**POP, **R_MOV, "with_genres": "80"}, 3000, None),
    ("Drugs & Excess",      {**POP}, 1000, ["drug addiction", "drugs", "cocaine"]),
    ("Disturbing & Dark",   {**POP}, 1000, ["psychopath", "disturbing", "cannibalism"]),
    ("Indian A-Rated",      {**POP, "certification_country": "IN", "certification": "A", "with_origin_country": "IN"}, 3000, None),
 ]),
 ("adult-series", T, "🔞  18+ Series", {}, None, [
    ("Trending 18+",        {**POP, **MA_TV, "air_date.gte": SINCE(365)}, 500, None),
    ("All 18+ Series",      {**POP, **MA_TV}, MAX, None),
    ("Latest 18+",          {**LATEST_T, **MA_TV, "vote_count.gte": 5}, 500, None),
    ("Top Rated 18+",       {**RATED(200), **MA_TV}, 2000, None),
    ("Steamy & Explicit",   {**POP}, 3000, ["nudity", "sex scene", "female nudity"]),
    ("Brutal & Violent",    {**POP}, 3000, ["violence", "graphic violence", "brutality"]),
    ("Crime & Gangster",    {**POP, **MA_TV, "with_genres": "80"}, 2000, None),
    ("Fantasy & War Epics", {**POP, **MA_TV, "with_genres": "10765|10768"}, 1500, None),
    ("Dark Comedy",         {**POP, **MA_TV, "with_genres": "35"}, 1500, None),
    ("Drugs & Excess",      {**POP}, 1000, ["drug addiction", "drugs", "drug dealer"]),
 ]),
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
            if e.code in (404, 422):
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

KW, PEOPLE = {}, {}
def keyword_id(name):
    if name not in KW:
        res = get("search/keyword", {"query": name}).get("results") or []
        exact = [k for k in res if k["name"].lower() == name.lower()]
        KW[name] = str((exact or res or [{"id": ""}])[0]["id"] or "")
    return KW[name]

def person_id(spec):
    if spec not in PEOPLE:
        names = [n.lower() for n in spec.split(":")]
        res = get("search/person", {"query": spec.split(":")[0]}).get("results") or []
        ok = [r for r in res if r.get("name", "").lower() in names] or res
        ok.sort(key=lambda r: -(r.get("popularity") or 0))
        PEOPLE[spec] = str(ok[0]["id"]) if ok else ""
    return PEOPLE[spec]

CACHE_D = {}
def imdb_ids(keys):
    need = sorted(k for k in keys if k not in CACHE_D)
    def one(k):
        typ, tid = k.split(":")
        return k, (get(f"{typ}/{tid}/external_ids").get("imdb_id") or "")
    with cf.ThreadPoolExecutor(16) as ex:
        for k, v in ex.map(one, need):
            CACHE_D[k] = v
    print(f"  mapped {len(need)} new titles to IMDb ids")

GENRES = {}
def to_meta(r, typ):
    iid = CACHE_D.get(f"{tt(typ)}:{r['id']}")
    if not iid:
        return None
    rating = r.get("vote_average") or 0
    yr = (r.get("first_air_date") or r.get("release_date") or "")[:4]
    ov = (r.get("overview") or "").strip()
    if len(ov) > 200:
        ov = ov[:197].rsplit(" ", 1)[0] + "…"
    head = " · ".join(x for x in [f"★ {rating:.1f}" if rating else "", yr] if x)
    m = {"id": iid, "type": typ, "name": r.get("name") or r.get("title"), "posterShape": "poster",
         "releaseInfo": yr, "description": (head + ("\n" + ov if ov else "")).strip(),
         "genres": [GENRES[g] for g in (r.get("genre_ids") or []) if g in GENRES][:3]}
    if rating:
        m["imdbRating"] = f"{rating:.1f}"
    if r.get("poster_path"):
        m["poster"] = IMG + "w500" + r["poster_path"]
    if r.get("backdrop_path"):
        m["background"] = IMG + "w1280" + r["backdrop_path"]
    return m

# ============================================================================
# Build
# ============================================================================
def fetch_sub(typ, base, base_kw, sub):
    label, extra, maxn, kws = sub
    p = {"include_adult": "false", **base, **extra}
    cast = p.pop("_cast", None)
    if cast:
        pid = person_id(cast)
        if not pid:
            return []
        p["with_cast"] = pid
        p.pop("with_original_language", None)   # filmography in every language
    names = kws or base_kw
    if names:
        ids = [i for i in (keyword_id(k) for k in names) if i]
        if not ids:
            return []
        p["with_keywords"] = "|".join(ids)
    res = paged(f"discover/{tt(typ)}", p, maxn)
    if not res and p.get("certification") == "TV-MA":       # TMDB TV certification filter unsupported -> keywords
        p.pop("certification"); p.pop("certification_country")
        ids = [i for i in (keyword_id(k) for k in MA_TV_FALLBACK_KW) if i]
        p["with_keywords"] = "|".join(ids)
        res = paged(f"discover/{tt(typ)}", p, maxn)
    return res

def write_pages(base_dir, stem, metas):
    """stem '' -> default catalog file; stem 'genre=X' -> filtered pages."""
    os.makedirs(base_dir, exist_ok=True)
    n = len(metas)
    for i in range(0, max(n, 1), PAGE):
        if stem:
            name = f"{stem}.json" if i == 0 else f"{stem}&skip={i}.json"
        else:
            name = None if i == 0 else f"skip={i}.json"
        path = (base_dir + ".json") if name is None else os.path.join(base_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"metas": metas[i:i + PAGE]}, f, ensure_ascii=False, separators=(",", ":"))
    end = ((n - 1) // PAGE + 1) * PAGE if n else PAGE
    with open(os.path.join(base_dir, (f"{stem}&skip={end}.json" if stem else f"skip={end}.json")), "w") as f:
        f.write('{"metas":[]}')

def build():
    if not KEY and get is _get_real:
        sys.exit("Set TMDB_API_KEY (repo secret).")
    t0 = time.time()
    try:
        CACHE_D.update(json.load(open(CACHE, encoding="utf-8")))
    except Exception:
        pass
    for typ in ("tv", "movie"):
        for g in get(f"genre/{typ}/list").get("genres", []):
            GENRES[g["id"]] = g["name"]

    jobs = [(gi, si, g, s) for gi, g in enumerate(GROUPS) for si, s in enumerate(g[5])]
    results = {}
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(fetch_sub, g[1], g[3], g[4], s): (gi, si) for gi, si, g, s in jobs}
        for f in cf.as_completed(futs):
            results[futs[f]] = f.result()
    imdb_ids({f"{tt(GROUPS[gi][1])}:{r['id']}" for (gi, si), rs in results.items() for r in rs})

    # previous version's shelves go below the top catalogs
    legacy = []
    if INCLUDE_LEGACY:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import legacy_v3
        legacy = legacy_v3.build_legacy(get, CACHE_D, GENRES)

    shutil.rmtree(os.path.join(ROOT, "catalog"), ignore_errors=True)
    catalogs, total, uniq = [], 0, set()
    for gi, (cid, typ, name, base, base_kw, subs) in enumerate(GROUPS):
        base_dir = os.path.join(ROOT, "catalog", typ, cid)
        options, default_written = [], False
        for si, sub in enumerate(subs):
            metas, seen = [], set()
            for r in results.get((gi, si), []):
                m = to_meta(r, typ)
                if m and m["id"] not in seen:
                    seen.add(m["id"]); metas.append(m)
            print(f"  {len(metas):6d}  {cid} / {sub[0]}")
            if not metas:
                continue
            label = sub[0].replace("&", "and")          # keep URLs clean
            options.append(label)
            write_pages(base_dir, "genre=" + label, metas)
            if not default_written:                        # first non-empty sub = Home row
                write_pages(base_dir, "", metas); default_written = True
            total += len(metas); uniq |= seen
        if options:
            catalogs.append({"type": typ, "id": cid, "name": name,
                             "genres": options,
                             "extra": [{"name": "genre", "options": options, "isRequired": False},
                                       {"name": "skip", "isRequired": False}],
                             "extraSupported": ["genre", "skip"]})

    for cid, typ, name, metas in legacy:
        if not metas or any(c["id"] == cid for c in catalogs):
            continue
        write_pages(os.path.join(ROOT, "catalog", typ, cid), "", metas)
        catalogs.append({"type": typ, "id": cid, "name": name, "extra": [{"name": "skip", "isRequired": False}]})
        total += len(metas); uniq |= {m["id"] for m in metas}
    print(f"  + {sum(1 for x in legacy if x[3])} legacy shelves")

    manifest = {
        "id": "com.sayand.nuvio.collections",
        "version": VERSION,
        "name": "Sayand's Collections",
        "description": "Top: Sitcoms, Malayalam, Tamil, 18+ Movies, 18+ Series with subcategory filters. "
                       "Below: 170+ shelves (trending, anime, platforms, moods, Indian, recommender). Rebuilt daily from TMDB.",
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
    print(f"built {len(catalogs)} catalogs · {total} entries · {len(uniq)} unique · {time.time() - t0:.0f}s")

# ============================================================================
# Offline self-test
# ============================================================================
def _fake_get(path, params=None):
    params = params or {}
    rnd = random.Random(path + json.dumps(params, sort_keys=True))
    if path.startswith("genre/"):
        return {"genres": [{"id": 35, "name": "Comedy"}, {"id": 18, "name": "Drama"}]}
    if path == "search/keyword":
        return {"results": [{"id": abs(hash(params["query"])) % 99999, "name": params["query"]}]}
    if path == "search/person":
        return {"results": [{"id": 4242, "name": params["query"], "popularity": 9}]}
    if path.endswith("external_ids"):
        tid = int(path.split("/")[1])
        return {"imdb_id": "" if tid % 17 == 0 else f"tt{tid:07d}"}
    if params.get("certification") == "TV-MA":
        return {"results": [], "total_pages": 0}          # exercise the fallback
    total_pages = 4 if "with_keywords" in params else 30
    res = [{"id": rnd.randint(1, 900000), "name": f"Show {rnd.randint(1, 9999)}", "title": f"Film {rnd.randint(1, 9999)}",
            "vote_average": round(rnd.uniform(5, 9.3), 1), "first_air_date": "1994-01-01", "release_date": "2001-01-01",
            "genre_ids": [35], "overview": "x " * 150, "poster_path": "/p.jpg"} for _ in range(20)]
    return {"results": res, "total_pages": total_pages}

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        get = _fake_get
        ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest")
        CACHE = os.path.join(ROOT, "data", "imdb_cache.json")
        shutil.rmtree(ROOT, ignore_errors=True)
    build()
