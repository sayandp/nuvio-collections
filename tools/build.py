#!/usr/bin/env python3
"""
Sayand's Nuvio / Stremio catalog add-on  —  static build.

  python build.py            -> builds ./site  (offline, uses IDs below)
  python build.py --resolve  -> also checks every IMDb ID against Cinemeta,
                                fixes wrong ones, fills missing ones (needs internet)

Edit FAV_SERIES / FAV_MOVIES / the shelves below, re-run, push ./site to GitHub Pages.
Install in Nuvio:  Settings > Add-ons > Install from URL >  https://<you>.github.io/<repo>/manifest.json
"""
import json, math, os, re, shutil, sys, time, urllib.parse, urllib.request
from collections import Counter

VERSION = "1.0.0"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root = published site
POSTER = "https://images.metahub.space/poster/medium/{}/img"
BG = "https://images.metahub.space/background/medium/{}/img"

# ---------------------------------------------------------------------------
# TITLE DATABASE   name : (imdb_id or None, year, type, tags)
# tags drive the recommender: genres + vibe + origin + platform
# ---------------------------------------------------------------------------
S, M = "series", "movie"
DB = {
 # ---------- sitcoms 70s
 "M*A*S*H": ("tt0068098", 1972, S, "sitcom 70s war workplace ensemble us"),
 "All in the Family": ("tt0066626", 1971, S, "sitcom 70s family multicam us"),
 "Happy Days": ("tt0070992", 1974, S, "sitcom 70s family nostalgia us"),
 "The Mary Tyler Moore Show": ("tt0065314", 1970, S, "sitcom 70s workplace us"),
 "Taxi": ("tt0077089", 1978, S, "sitcom 70s workplace ensemble us"),
 "Three's Company": ("tt0075596", 1977, S, "sitcom 70s friends farce us"),
 "Fawlty Towers": ("tt0072500", 1975, S, "sitcom 70s farce workplace uk british"),
 "The Jeffersons": ("tt0072519", 1975, S, "sitcom 70s family us"),
 # ---------- 80s
 "Cheers": ("tt0083399", 1982, S, "sitcom 80s workplace friends ensemble us"),
 "The Golden Girls": ("tt0088526", 1985, S, "sitcom 80s friends us"),
 "Family Ties": ("tt0083413", 1982, S, "sitcom 80s family us"),
 "Night Court": ("tt0086770", 1984, S, "sitcom 80s workplace us"),
 "Married... with Children": ("tt0092400", 1987, S, "sitcom 80s family cringe us"),
 "Roseanne": ("tt0094540", 1988, S, "sitcom 80s family us"),
 "Blackadder": ("tt0088484", 1983, S, "sitcom 80s period satire uk british"),
 "Only Fools and Horses": ("tt0081912", 1981, S, "sitcom 80s family uk british"),
 # ---------- 90s
 "Seinfeld": ("tt0098904", 1989, S, "sitcom 90s friends cringe observational us"),
 "Friends": ("tt0108778", 1994, S, "sitcom 90s friends ensemble romance us comfort"),
 "Frasier": ("tt0106004", 1993, S, "sitcom 90s family workplace witty us"),
 "Everybody Loves Raymond": ("tt0115167", 1996, S, "sitcom 90s family us comfort"),
 "The Fresh Prince of Bel-Air": ("tt0098800", 1990, S, "sitcom 90s family us comfort"),
 "Home Improvement": ("tt0101120", 1991, S, "sitcom 90s family us"),
 "That '70s Show": ("tt0165598", 1998, S, "sitcom 90s friends nostalgia us"),
 "Will & Grace": ("tt0157246", 1998, S, "sitcom 90s friends us"),
 "Mr. Bean": ("tt0096657", 1990, S, "sitcom 90s slapstick uk british"),
 # ---------- 2000s
 "The Office": ("tt0386676", 2005, S, "sitcom 00s workplace mockumentary cringe us comfort"),
 "The Office (UK)": ("tt0290978", 2001, S, "sitcom 00s workplace mockumentary cringe uk british"),
 "Arrested Development": ("tt0367279", 2003, S, "sitcom 00s family cringe witty us"),
 "Scrubs": ("tt0285403", 2001, S, "sitcom 00s workplace hospital us"),
 "How I Met Your Mother": ("tt0460649", 2005, S, "sitcom 00s friends romance us comfort"),
 "30 Rock": ("tt0496424", 2006, S, "sitcom 00s workplace witty us"),
 "Curb Your Enthusiasm": ("tt0264235", 2000, S, "sitcom 00s cringe hbo us"),
 "The Big Bang Theory": ("tt0898266", 2007, S, "sitcom 00s friends nerd us"),
 "Malcolm in the Middle": ("tt0212671", 2000, S, "sitcom 00s family us"),
 "It's Always Sunny in Philadelphia": ("tt0472954", 2005, S, "sitcom 00s friends dark-comedy us"),
 "Two and a Half Men": ("tt0369179", 2003, S, "sitcom 00s family us"),
 # ---------- 2010s
 "Parks and Recreation": ("tt1266020", 2009, S, "sitcom 10s workplace mockumentary comfort us"),
 "Modern Family": ("tt1442437", 2009, S, "sitcom 10s family mockumentary comfort us"),
 "Brooklyn Nine-Nine": ("tt2467372", 2013, S, "sitcom 10s workplace cop comfort us"),
 "Community": ("tt1439629", 2009, S, "sitcom 10s friends meta us"),
 "Schitt's Creek": ("tt3526078", 2015, S, "sitcom 10s family comfort canada"),
 "The Good Place": ("tt4955642", 2016, S, "sitcom 10s friends fantasy philosophy us"),
 "Silicon Valley": ("tt2575988", 2014, S, "sitcom 10s workplace tech hbo us"),
 "New Girl": ("tt1826940", 2011, S, "sitcom 10s friends romance us"),
 "Veep": ("tt1759761", 2012, S, "sitcom 10s workplace politics satire hbo us"),
 "Fleabag": ("tt5687612", 2016, S, "sitcom 10s dark-comedy uk british prime"),
 "Superstore": ("tt4477976", 2015, S, "sitcom 10s workplace us"),
 "What We Do in the Shadows": ("tt7908628", 2019, S, "sitcom 10s mockumentary horror-comedy fx hulu us"),
 # ---------- 2020s
 "Abbott Elementary": ("tt14218830", 2021, S, "sitcom 20s workplace mockumentary comfort hulu us"),
 "Ted Lasso": ("tt10986410", 2020, S, "sitcom 20s workplace sports comfort apple us"),
 "Only Murders in the Building": ("tt11691774", 2021, S, "sitcom 20s mystery friends hulu us"),
 "Ghosts": ("tt11379026", 2021, S, "sitcom 20s supernatural family us"),
 "Hacks": ("tt11815682", 2021, S, "sitcom 20s workplace hbo us"),
 "Shrinking": ("tt15677150", 2023, S, "sitcom 20s workplace comfort apple us"),
 "Reservation Dogs": ("tt13623580", 2021, S, "sitcom 20s friends coming-of-age fx hulu us"),
 # ---------- India comedy
 "Sarabhai vs Sarabhai": ("tt1518542", 2004, S, "sitcom india hindi family comfort"),
 "Panchayat": ("tt12004706", 2020, S, "sitcom india hindi village workplace comfort prime"),
 "Gullak": ("tt10530900", 2019, S, "sitcom india hindi family comfort"),
 "Pitchers": ("tt4742876", 2015, S, "comedy-drama india hindi friends startup"),
 "Kota Factory": ("tt9432978", 2019, S, "drama india hindi coming-of-age netflix"),
 "Uppum Mulakum": (None, 2015, S, "sitcom india malayalam family comfort"),

 # ---------- Netflix originals
 "Stranger Things": ("tt4574334", 2016, S, "netflix scifi horror coming-of-age 80s-vibe us"),
 "Dark": ("tt5753856", 2017, S, "netflix scifi mystery time-travel german international"),
 "Money Heist": ("tt6468322", 2017, S, "netflix crime heist thriller spanish international"),
 "The Crown": ("tt4786824", 2016, S, "netflix drama period royal uk british"),
 "Narcos": ("tt2707408", 2015, S, "netflix crime drugs thriller true-story violence"),
 "Narcos: Mexico": ("tt8714904", 2018, S, "netflix crime drugs thriller true-story mexico international violence"),
 "Mindhunter": ("tt5290382", 2017, S, "netflix crime psychological true-story us"),
 "Squid Game": ("tt10919420", 2021, S, "netflix thriller survival korean international violence"),
 "Wednesday": ("tt13443470", 2022, S, "netflix mystery comedy supernatural teen us"),
 "BoJack Horseman": ("tt3398228", 2014, S, "netflix animation dark-comedy adult us"),
 "Ozark": ("tt5071412", 2017, S, "netflix crime thriller family us violence"),
 "The Witcher": ("tt5180504", 2019, S, "netflix fantasy action violence nudity"),
 "Black Mirror": ("tt2085059", 2011, S, "netflix scifi anthology dystopia uk british"),
 "Bridgerton": ("tt8740790", 2020, S, "netflix romance period drama nudity"),
 "Sacred Games": ("tt6077448", 2018, S, "netflix crime thriller india hindi violence nudity"),
 "Delhi Crime": ("tt9398640", 2019, S, "netflix crime true-story india hindi"),
 "Lupin": ("tt2531336", 2021, S, "netflix heist mystery french international"),
 "Arcane": ("tt11126994", 2021, S, "netflix animation fantasy action"),
 "3 Body Problem": ("tt13016388", 2024, S, "netflix scifi mystery"),
 "Beef": ("tt14403178", 2023, S, "netflix dark-comedy drama us"),
 "Alice in Borderland": ("tt10795658", 2020, S, "netflix thriller survival japanese international violence"),
 "Elite": ("tt7134908", 2018, S, "netflix teen thriller mystery spanish international nudity"),
 "Kingdom": ("tt6611916", 2019, S, "netflix horror zombie period korean international violence"),
 "Better Call Saul": ("tt3032476", 2015, S, "netflix crime drama legal us"),

 # ---------- Prime Video originals
 "The Boys": ("tt1190634", 2019, S, "prime superhero satire dark action violence nudity"),
 "The Marvelous Mrs. Maisel": ("tt5788792", 2017, S, "prime comedy period standup us"),
 "Reacher": ("tt9288030", 2022, S, "prime action thriller crime us violence"),
 "Jack Ryan": ("tt5057054", 2018, S, "prime action thriller spy us"),
 "Mirzapur": ("tt6473300", 2018, S, "prime crime gangster india hindi violence"),
 "The Family Man": ("tt9544034", 2019, S, "prime action spy thriller india hindi comedy"),
 "Paatal Lok": ("tt9680440", 2020, S, "prime crime thriller india hindi violence"),
 "Invincible": ("tt6741278", 2021, S, "prime animation superhero action violence"),
 "The Lord of the Rings: The Rings of Power": ("tt7631058", 2022, S, "prime fantasy epic"),
 "Fallout": ("tt12637874", 2024, S, "prime scifi post-apocalyptic dark-comedy violence"),
 "Gen V": ("tt13159924", 2023, S, "prime superhero teen satire violence nudity"),
 "Good Omens": ("tt1869454", 2019, S, "prime fantasy comedy uk british"),

 # ---------- Hulu / FX
 "The Handmaid's Tale": ("tt5834204", 2017, S, "hulu drama dystopia violence"),
 "The Bear": ("tt14452776", 2022, S, "hulu fx drama comedy workplace kitchen us"),
 "Shōgun": ("tt2788316", 2024, S, "hulu fx drama period war japanese epic violence"),
 "Normal People": ("tt9059760", 2020, S, "hulu romance drama irish nudity"),
 "The Great": ("tt2235759", 2020, S, "hulu comedy period satire royal nudity"),
 "Atlanta": ("tt4288182", 2016, S, "fx hulu comedy surreal us"),
 "Fargo": ("tt2802850", 2014, S, "fx hulu crime dark-comedy anthology violence"),

 # ---------- HBO / Max
 "Game of Thrones": ("tt0944947", 2011, S, "hbo fantasy epic war politics violence nudity"),
 "House of the Dragon": ("tt11198330", 2022, S, "hbo fantasy epic war politics violence nudity"),
 "The Sopranos": ("tt0141842", 1999, S, "hbo crime mafia drama violence"),
 "The Wire": ("tt0306414", 2002, S, "hbo crime drama city us"),
 "Succession": ("tt7660850", 2018, S, "hbo drama family power satire"),
 "True Detective": ("tt2356777", 2014, S, "hbo crime mystery anthology dark violence"),
 "Chernobyl": ("tt7366338", 2019, S, "hbo drama true-story disaster miniseries"),
 "The Last of Us": ("tt3581920", 2023, S, "hbo drama post-apocalyptic horror violence"),
 "Euphoria": ("tt8772296", 2019, S, "hbo teen drama drugs nudity"),
 "Westworld": ("tt0475784", 2016, S, "hbo scifi mystery violence nudity"),
 "The White Lotus": ("tt13406094", 2021, S, "hbo dark-comedy satire anthology nudity"),
 "Barry": ("tt5348176", 2018, S, "hbo dark-comedy crime violence"),
 "Band of Brothers": ("tt0185906", 2001, S, "hbo war drama true-story miniseries violence"),
 "Rome": ("tt0384766", 2005, S, "hbo period drama epic politics violence nudity"),
 "Boardwalk Empire": ("tt0979432", 2010, S, "hbo crime period gangster violence nudity"),
 "Deadwood": ("tt0348914", 2004, S, "hbo western period drama violence"),
 "The Penguin": ("tt15435876", 2024, S, "hbo crime gangster superhero violence"),

 # ---------- Apple TV+
 "Severance": ("tt11280740", 2022, S, "apple scifi mystery workplace psychological"),
 "Slow Horses": ("tt5875444", 2022, S, "apple spy thriller dark-comedy uk british"),
 "The Morning Show": ("tt7203552", 2019, S, "apple drama workplace media"),
 "For All Mankind": ("tt7772588", 2019, S, "apple scifi space alt-history drama"),
 "Silo": ("tt14688458", 2023, S, "apple scifi dystopia mystery"),
 "Pachinko": ("tt8888540", 2022, S, "apple drama period family korean international"),

 # ---------- international / UK / other
 "Crash Landing on You": ("tt10850932", 2019, S, "netflix romance comedy korean international comfort"),
 "Extraordinary Attorney Woo": ("tt20869502", 2022, S, "netflix legal comedy-drama korean international comfort"),
 "Reply 1988": ("tt5182866", 2015, S, "comedy-drama family nostalgia korean international comfort"),
 "Babylon Berlin": ("tt4378376", 2017, S, "crime period noir german international violence nudity"),
 "Borgen": ("tt1526318", 2010, S, "drama politics danish international"),
 "Fauda": ("tt4565380", 2015, S, "netflix action thriller israeli international violence"),
 "Scam 1992": ("tt12392504", 2020, S, "drama true-story finance india hindi"),
 "Peaky Blinders": ("tt2442560", 2013, S, "netflix crime period gangster uk british violence"),
 "Sherlock": ("tt1475582", 2010, S, "crime mystery detective uk british"),
 "Line of Duty": ("tt2303687", 2012, S, "crime thriller police uk british"),
 "Broadchurch": ("tt2249364", 2013, S, "crime mystery drama uk british"),
 "Happy Valley": ("tt3428912", 2014, S, "crime drama police uk british violence"),
 "Breaking Bad": ("tt0903747", 2008, S, "crime drama drugs thriller us violence"),
 "Spartacus": ("tt1442449", 2010, S, "period action epic gladiator violence nudity"),
 "Vikings": ("tt2306299", 2013, S, "period action epic war violence"),
 "Outlander": ("tt3006802", 2014, S, "period romance fantasy time-travel nudity violence"),
 "Banshee": ("tt2017109", 2013, S, "crime action thriller violence nudity"),
 "Dexter": ("tt0773262", 2006, S, "crime thriller serial-killer dark violence"),
 "Hannibal": ("tt2243973", 2013, S, "crime horror psychological serial-killer violence"),
 "True Blood": ("tt0844441", 2008, S, "hbo horror vampire romance violence nudity"),
 "The Deuce": ("tt3809276", 2017, S, "hbo drama period crime nudity"),

 # ---------- movies
 "The Shawshank Redemption": ("tt0111161", 1994, M, "drama prison hope classic"),
 "The Godfather": ("tt0068646", 1972, M, "crime mafia drama classic violence"),
 "The Dark Knight": ("tt0468569", 2008, M, "superhero crime thriller action"),
 "Inception": ("tt1375666", 2010, M, "scifi heist mind-bending thriller nolan"),
 "Interstellar": ("tt0816692", 2014, M, "scifi space drama nolan"),
 "Oppenheimer": ("tt15398776", 2023, M, "drama true-story history nolan"),
 "Parasite": ("tt6751668", 2019, M, "thriller dark-comedy class korean international"),
 "Pulp Fiction": ("tt0110912", 1994, M, "crime dark-comedy classic violence"),
 "Fight Club": ("tt0137523", 1999, M, "drama psychological dark violence"),
 "Whiplash": ("tt2582802", 2014, M, "drama music intense"),
 "Joker": ("tt7286456", 2019, M, "drama psychological crime dark violence"),
 "Spirited Away": ("tt0245429", 2001, M, "animation fantasy japanese international comfort"),
 "Dune: Part Two": ("tt15239678", 2024, M, "scifi epic war"),
 "Everything Everywhere All at Once": ("tt6710474", 2022, M, "scifi comedy multiverse family"),
 "Drishyam": ("tt3417422", 2013, M, "thriller crime family india malayalam"),
 "Kumbalangi Nights": ("tt8413338", 2019, M, "drama family comfort india malayalam"),
 "Premam": ("tt4679210", 2015, M, "romance comedy coming-of-age india malayalam comfort"),
 "Bangalore Days": ("tt3668162", 2014, M, "comedy-drama friends family india malayalam comfort"),
 "Manjummel Boys": (None, 2024, M, "thriller survival friends true-story india malayalam"),
 "Se7en": ("tt0114369", 1995, M, "crime thriller serial-killer dark violence"),
 "Prisoners": ("tt1392214", 2013, M, "crime thriller mystery dark"),
 "Gone Girl": ("tt2267998", 2014, M, "thriller mystery psychological"),
 "Zodiac": ("tt0443706", 2007, M, "crime mystery true-story"),
 "Oldboy": ("tt0364569", 2003, M, "thriller revenge korean international violence"),
 "Memories of Murder": ("tt0353969", 2003, M, "crime mystery true-story korean international"),
 "The Prestige": ("tt0482571", 2006, M, "thriller mystery period nolan"),
 "Arrival": ("tt2543164", 2016, M, "scifi drama mind-bending"),
 "Blade Runner 2049": ("tt1856101", 2017, M, "scifi noir epic"),
 "Mad Max: Fury Road": ("tt1392190", 2015, M, "action post-apocalyptic violence"),
 "Your Name.": ("tt5311514", 2016, M, "animation romance fantasy japanese international comfort"),
 "The Grand Budapest Hotel": ("tt2278388", 2014, M, "comedy period whimsical comfort"),
 "Superbad": ("tt0829482", 2007, M, "comedy friends coming-of-age"),
 "The Departed": ("tt0407887", 2006, M, "crime thriller gangster violence"),
 "Goodfellas": ("tt0099685", 1990, M, "crime mafia true-story classic violence"),
 "Andhadhun": ("tt8108198", 2018, M, "thriller dark-comedy india hindi"),
 "Gangs of Wasseypur": ("tt1954470", 2012, M, "crime gangster india hindi violence"),
 "3 Idiots": ("tt1187043", 2009, M, "comedy-drama friends coming-of-age india hindi comfort"),
}

# ---------------------------------------------------------------------------
# YOUR FAVOURITES  (edit freely — the recommender learns from these)
# ---------------------------------------------------------------------------
FAV_SERIES = ["Breaking Bad", "Game of Thrones", "Friends", "The Office", "Dark",
              "Peaky Blinders", "Money Heist", "Panchayat", "Sherlock", "Chernobyl",
              "Stranger Things", "Better Call Saul", "The Boys", "Brooklyn Nine-Nine"]
FAV_MOVIES = ["Interstellar", "Inception", "The Dark Knight", "Parasite", "Drishyam",
              "Kumbalangi Nights", "Premam", "The Shawshank Redemption", "Whiplash", "Joker"]

# ---------------------------------------------------------------------------
# SHELVES  (catalog id, type, display name, list of titles or a filter)
# ---------------------------------------------------------------------------
def by_tag(*need, typ=S, exclude=()):
    return [n for n, v in DB.items() if v[2] == typ and all(t in v[3].split() for t in need)
            and not any(x in v[3].split() for x in exclude)]

ERAS = [("70s", "70s"), ("80s", "80s"), ("90s", "90s"), ("00s", "2000s"), ("10s", "2010s"), ("20s", "2020s")]
SHELVES = []
SHELVES.append(("fav-series", S, "★ My Favourite Series", FAV_SERIES))
SHELVES.append(("fav-movies", M, "★ My Favourite Movies", FAV_MOVIES))
# For You / Because you like X are appended later by the recommender
for tag, label in ERAS:
    SHELVES.append((f"sitcom-{tag}", S, f"Sitcoms of the {label}", by_tag("sitcom", tag)))
SHELVES.append(("sitcom-india", S, "Indian Comedy Shelf", by_tag("india", typ=S, exclude=("crime",))))
SHELVES.append(("netflix", S, "Netflix Originals", by_tag("netflix")))
SHELVES.append(("prime", S, "Prime Video Originals", by_tag("prime")))
SHELVES.append(("hulu", S, "Hulu & FX", sorted(set(by_tag("hulu") + by_tag("fx")))))
SHELVES.append(("hbo", S, "HBO & Max", by_tag("hbo")))
SHELVES.append(("apple", S, "Apple TV+", by_tag("apple")))
SHELVES.append(("international", S, "International Series Mix", by_tag("international")))
SHELVES.append(("british", S, "British Series", by_tag("british")))
SHELVES.append(("india-series", S, "Indian Series", by_tag("india")))
SHELVES.append(("comfort", S, "Comfort Watch", by_tag("comfort")))
SHELVES.append(("after-dark-violence", S, "After Dark 18+ · Brutal & Violent", by_tag("violence")))
SHELVES.append(("after-dark-explicit", S, "After Dark 18+ · Explicit", by_tag("nudity")))
SHELVES.append(("epic-fantasy", S, "Epic Fantasy & Period Wars",
                sorted(set(by_tag("fantasy") + by_tag("epic")), key=lambda n: -DB[n][1])))
SHELVES.append(("crime", S, "Crime & Gangsters", sorted(set(by_tag("crime")), key=lambda n: -DB[n][1])))
SHELVES.append(("malayalam-movies", M, "Malayalam Favourites", by_tag("malayalam", typ=M)))
SHELVES.append(("mind-bending", M, "Mind-Bending Movies",
                sorted(set(by_tag("mind-bending", typ=M) + by_tag("nolan", typ=M) + by_tag("mystery", typ=M)))))

# ---------------------------------------------------------------------------
# RECOMMENDER  — content-based, TF-IDF over tags, profile = your favourites
# ---------------------------------------------------------------------------
STOP = {"series", "us"}
def vec(name, idf):
    tags = [t for t in DB[name][3].split() if t not in STOP]
    c = Counter(tags)
    return {t: c[t] * idf.get(t, 0) for t in c}

def cos(a, b):
    num = sum(a[t] * b.get(t, 0) for t in a)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0

def recommend(favs, typ, k=30):
    pool = [n for n, v in DB.items() if v[2] == typ]
    df = Counter(t for n in pool for t in set(DB[n][3].split()))
    idf = {t: math.log(len(pool) / df[t]) + 1 for t in df}
    fv = {f: vec(f, idf) for f in favs if f in DB}
    prof = Counter()
    for v in fv.values():
        prof.update(v)
    out = []
    for n in pool:
        if n in favs:
            continue
        v = vec(n, idf)
        s = cos(v, prof)
        best = max(fv, key=lambda f: cos(v, fv[f])) if fv else None
        out.append((s, n, best))
    out.sort(reverse=True)
    return out[:k], fv, idf

def because(fav, fv, idf, typ, exclude, k=15):
    pool = [n for n, v in DB.items() if v[2] == typ and n not in exclude]
    sc = sorted(((cos(vec(n, idf), fv[fav]), n) for n in pool), reverse=True)
    return [n for s, n in sc[:k] if s > 0]

WHY = {}   # name -> reason text shown in description

def add_recs():
    for typ, favs, label in ((S, FAV_SERIES, "Series"), (M, FAV_MOVIES, "Movies")):
        recs, fv, idf = recommend(favs, typ)
        for s, n, best in recs:
            WHY.setdefault(n, f"Recommended · {int(s*100)}% match · because you like {best}")
        SHELVES.insert(2, (f"for-you-{typ}", typ, f"For You · {label}", [n for _, n, _ in recs]))
        # "Because you like X" for your first 3 favourites
        for fav in favs[:3]:
            items = because(fav, fv, idf, typ, set(favs))
            slug = re.sub(r"[^a-z0-9]+", "-", fav.lower()).strip("-")
            SHELVES.append((f"because-{slug}", typ, f"Because you like {fav}", items))

# ---------------------------------------------------------------------------
# OPTIONAL: verify / fix IMDb IDs via Cinemeta (run on your own PC)
# ---------------------------------------------------------------------------
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nuvio-addon-builder"}), timeout=15) as r:
        return json.load(r)

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def resolve():
    fixed = 0
    for name, (iid, year, typ, tags) in list(DB.items()):
        ok = False
        if iid:
            try:
                m = get(f"https://v3-cinemeta.strem.io/meta/{typ}/{iid}.json").get("meta") or {}
                ok = norm(m.get("name", ""))[:6] == norm(name)[:6]
            except Exception:
                ok = False
        if ok:
            continue
        q = urllib.parse.quote(re.sub(r"\s*\(.*?\)", "", name))
        try:
            res = get(f"https://v3-cinemeta.strem.io/catalog/{typ}/top/search={q}.json").get("metas", [])
        except Exception as e:
            print("  search failed:", name, e); continue
        def yr(m):
            try: return int(str(m.get("releaseInfo", "0"))[:4])
            except ValueError: return 0
        res.sort(key=lambda m: (norm(m.get("name", "")) != norm(name), abs(yr(m) - year)))
        if res:
            new = res[0]["id"]
            print(f"  {'FIX ' if iid else 'ADD '}{name}: {iid} -> {new} ({res[0].get('name')}, {res[0].get('releaseInfo')})")
            DB[name] = (new, year, typ, tags); fixed += 1
        time.sleep(0.15)
    print(f"resolve: {fixed} IDs fixed/added")
    # write back so next offline build uses the fixed IDs
    src = open(__file__, encoding="utf-8").read()
    for name, (iid, *_rest) in DB.items():
        if iid:
            pat = re.compile(r'(\n \s*' + re.escape(json.dumps(name, ensure_ascii=False)) + r': \()(None|"tt\d+")')
            src = pat.sub(lambda m: m.group(1) + json.dumps(iid), src, count=1)
    open(__file__, "w", encoding="utf-8").write(src)

# ---------------------------------------------------------------------------
# BUILD STATIC ADD-ON
# ---------------------------------------------------------------------------
def meta(name):
    iid, year, typ, tags = DB[name]
    t = tags.split()
    genres = [g.replace("-", " ").title() for g in t if g not in STOP and not re.match(r"\d0s$", g)][:4]
    warn = [w for w in ("violence", "nudity", "drugs") if w in t]
    desc = WHY.get(name, "")
    if warn:
        desc = ("18+ · " + " · ".join(w.title() for w in warn) + (" · " + desc if desc else ""))
    return {"id": iid, "type": typ, "name": name, "releaseInfo": str(year),
            "poster": POSTER.format(iid), "background": BG.format(iid),
            "posterShape": "poster", "genres": genres, "description": desc or None}

def build():
    add_recs()
    shutil.rmtree(os.path.join(OUT, "catalog"), ignore_errors=True)
    catalogs, total = [], 0
    for cid, typ, cname, names in SHELVES:
        names = [n for n in dict.fromkeys(names) if n in DB and DB[n][0] and DB[n][2] == typ]
        if not names:
            continue
        metas = [{k: v for k, v in meta(n).items() if v is not None} for n in names]
        p = os.path.join(OUT, "catalog", typ)
        os.makedirs(p, exist_ok=True)
        with open(os.path.join(p, f"{cid}.json"), "w", encoding="utf-8") as f:
            json.dump({"metas": metas}, f, ensure_ascii=False, separators=(",", ":"))
        catalogs.append({"type": typ, "id": cid, "name": cname})
        total += len(metas)
    manifest = {
        "id": "com.sayand.nuvio.collections",
        "version": VERSION,
        "name": "Sayand's Collections",
        "description": "Personal favourites, sitcoms by era, Netflix / Prime / Hulu / HBO / Apple shelves, "
                       "international mix, After Dark 18+ and a taste-based recommender.",
        "logo": "https://images.metahub.space/poster/medium/tt0108778/img",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "catalogs": catalogs,
        "behaviorHints": {"configurable": False, "adult": False},
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write("<meta charset=utf-8><title>Sayand's Collections</title>"
                "<body style='font-family:sans-serif;background:#0b0b0b;color:#eee;padding:40px'>"
                "<h1>Sayand's Collections</h1><p>Install in Nuvio: copy this page's URL + "
                "<code>manifest.json</code></p>")
    print(f"built {len(catalogs)} catalogs, {total} entries -> {OUT}")
    for c in catalogs:
        print(f"  [{c['type']:6}] {c['id']:28} {c['name']}")

if __name__ == "__main__":
    if "--resolve" in sys.argv:
        resolve()
    build()
