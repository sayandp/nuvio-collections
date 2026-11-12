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
import json, math, os, random, re, shutil, sys, time, urllib.parse, urllib.request

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

  # ---------------- India: Malayalam, Tamil, Hindi, Telugu, Kannada
  ("ml-trending",     Mv, "Trending in Malayalam",        "🌴", "discover", {**POP, "with_original_language": "ml", "primary_release_date.gte": SINCE(150)}, 200),
  ("ml-this-year",    Mv, "Malayalam · New This Year",    "🆕", "discover", {**POP, "with_original_language": "ml", "primary_release_date.gte": f"{TODAY.year}-01-01"}, 300),
  ("ml-all",          Mv, "Every Malayalam Movie",        "🎞️", "discover", {**POP, "with_original_language": "ml"}, 5000),
  ("ml-best",         Mv, "Malayalam Masterpieces",       "🏆", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 40, "with_original_language": "ml"}, 500),
  ("ml-thrillers",    Mv, "Malayalam Thrillers",          "🔎", "discover", {**POP, "with_original_language": "ml", "with_genres": "53"}, 500),
  ("ml-comedy",       Mv, "Malayalam Comedy",             "😆", "discover", {**POP, "with_original_language": "ml", "with_genres": "35"}, 500),
  ("ml-family",       Mv, "Malayalam Family Drama",       "🏡", "discover", {**POP, "with_original_language": "ml", "with_genres": "10751|18"}, 500),
  ("ml-crime",        Mv, "Malayalam Crime & Mass",       "🔥", "discover", {**POP, "with_original_language": "ml", "with_genres": "80|28"}, 400),
  ("ml-80s-90s",      Mv, "Mollywood Golden Era · 80s & 90s","📼", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 10, "with_original_language": "ml", **dec(1980, 1999, "primary_release_date")}, 400),
  ("ml-series",       T,  "Malayalam Series",             "📺", "discover", {**POP, "with_original_language": "ml"}, 300),
  ("ml-mohanlal",     Mv, "Mohanlal Collection",          "🦁", "discover", {**POP, "_cast": "Mohanlal"}, 400),
  ("ml-mammootty",    Mv, "Mammootty Collection",         "👑", "discover", {**POP, "_cast": "Mammootty"}, 400),
  ("ml-fahadh",       Mv, "Fahadh Faasil Collection",     "🎭", "discover", {**POP, "_cast": "Fahadh Faasil"}, 150),
  ("ml-prithviraj",   Mv, "Prithviraj Collection",        "⚡", "discover", {**POP, "_cast": "Prithviraj Sukumaran"}, 150),
  ("ml-dulquer",      Mv, "Dulquer Salmaan Collection",   "🌟", "discover", {**POP, "_cast": "Dulquer Salmaan"}, 100),
  ("ta-trending",     Mv, "Trending in Tamil",            "🎺", "discover", {**POP, "with_original_language": "ta", "primary_release_date.gte": SINCE(150)}, 200),
  ("ta-all",          Mv, "Every Tamil Movie",            "🎞️", "discover", {**POP, "with_original_language": "ta"}, 5000),
  ("ta-best",         Mv, "Tamil Masterpieces",           "🏆", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 40, "with_original_language": "ta"}, 500),
  ("ta-action",       Mv, "Tamil Mass & Action",          "💥", "discover", {**POP, "with_original_language": "ta", "with_genres": "28"}, 500),
  ("ta-thrillers",    Mv, "Tamil Thrillers",              "🔎", "discover", {**POP, "with_original_language": "ta", "with_genres": "53|80"}, 400),
  ("ta-rajini",       Mv, "Rajinikanth Collection",       "😎", "discover", {**POP, "_cast": "Rajinikanth"}, 200),
  ("ta-vijay",        Mv, "Vijay Collection",             "🦅", "discover", {**POP, "_cast": "Vijay:Joseph Vijay"}, 120),
  ("ta-kamal",        Mv, "Kamal Haasan Collection",      "🎬", "discover", {**POP, "_cast": "Kamal Haasan"}, 250),
  ("ta-series",       T,  "Tamil Series",                 "📺", "discover", {**POP, "with_original_language": "ta"}, 300),
  ("hi-trending",     Mv, "Trending in Hindi",            "🪔", "discover", {**POP, "with_original_language": "hi", "primary_release_date.gte": SINCE(150)}, 200),
  ("hi-best",         Mv, "Bollywood Masterpieces",       "🏆", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 100, "with_original_language": "hi"}, 500),
  ("hi-all",          Mv, "Every Hindi Movie",            "🎞️", "discover", {**POP, "with_original_language": "hi"}, 5000),
  ("te-trending",     Mv, "Trending in Telugu",           "🌶️", "discover", {**POP, "with_original_language": "te", "primary_release_date.gte": SINCE(150)}, 200),
  ("te-best",         Mv, "Telugu Masterpieces",          "🏆", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 40, "with_original_language": "te"}, 400),
  ("kn-best",         Mv, "Kannada Masterpieces",         "🏆", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 25, "with_original_language": "kn"}, 300),
  ("india-series-best",T, "Best Indian Series",           "🇮🇳", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 30, "with_origin_country": "IN"}, 500),
  ("india-series-pop",T,  "Trending Indian Series",       "📈", "discover", {**POP, "with_origin_country": "IN", "first_air_date.gte": SINCE(730)}, 300),
  ("india-crime-series",T,"Indian Crime Thriller Series", "🕵️", "discover", {**POP, "with_origin_country": "IN", "with_genres": "80|9648"}, 300),

  # ---------------- sitcoms  (thousands, paginated)
  ("sitcoms-all",       T, "Every Sitcom Ever",          "😂", "discover", {**POP}, 5000, ["sitcom", "british sitcom", "family sitcom", "workplace comedy", "mockumentary", "multi-camera"]),
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
  ("mind-bending",     Mv, "Mind-Bending Twists",      "🧠", "discover", {**POP}, 300, ["twist ending", "plot twist", "nonlinear timeline", "mind bending", "unreliable narrator"]),
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
  ("cult-classics",    Mv, "Cult Classics",            "🦇", "discover", {**POP}, 200, ["cult film", "cult classic"]),
  ("martial-arts",     Mv, "Martial Arts",             "🥋", "discover", {**POP}, 200, ["martial arts"]),
  ("psych-thriller",   Mv, "Psychological Thrillers",  "🌀", "discover", {**POP}, 300, ["psychological thriller"]),
  ("revenge",          Mv, "Revenge Stories",          "🗡️", "discover", {**POP}, 200, ["revenge"]),
  ("feel-good",        Mv, "Feel-Good Movies",         "🌈", "discover", {**POP, "vote_average.gte": 6.5}, 200, ["feel-good", "feel good", "heartwarming", "uplifting"]),
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
  # ---------------- unlimited movies
  ("movies-all",       Mv, "Every Movie · Most Popular",   "♾️", "discover", {**POP, "vote_count.gte": 50}, 10000),
  ("movies-top-5000",  Mv, "Top 5000 Rated Movies",        "🥇", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 400}, 5000),
  ("series-all",       T,  "Every Series · Most Popular",  "♾️", "discover", {**POP, "vote_count.gte": 30}, 6000),
  ("movies-this-year", Mv, "Best Movies This Year",        "📅", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 80, "primary_release_date.gte": f"{TODAY.year}-01-01"}, 300),
  ("movies-last-year", Mv, "Best Movies Last Year",        "🗓️", "discover", {"sort_by": "vote_average.desc", "vote_count.gte": 150, **dec(TODAY.year - 1, TODAY.year - 1, "primary_release_date")}, 300),
  ("thriller",         Mv, "Edge-of-Seat Thrillers",       "😰", "discover", {**POP, "with_genres": "53"}, 1000),
  ("crime-movies",     Mv, "Crime Movies",                 "🚔", "discover", {**POP, "with_genres": "80"}, 800),
  ("mystery-movies",   Mv, "Mystery Movies",               "🗝️", "discover", {**POP, "with_genres": "9648"}, 500),
  ("fantasy-movies",   Mv, "Fantasy Worlds",               "🐉", "discover", {**POP, "with_genres": "14"}, 500),
  ("adventure",        Mv, "Big Adventures",               "🧭", "discover", {**POP, "with_genres": "12"}, 600),
  ("war-movies",       Mv, "War Movies",                   "🪖", "discover", {**POP, "with_genres": "10752"}, 300),
  ("westerns",         Mv, "Westerns",                     "🤠", "discover", {**POP, "with_genres": "37"}, 300),
  ("musicals",         Mv, "Music & Musicals",             "🎵", "discover", {**POP, "with_genres": "10402"}, 300),
  ("biopics",          Mv, "Biopics",                      "🧑‍🎤", "discover", {**POP}, 300, ["biography"]),
  ("courtroom",        Mv, "Courtroom Dramas",             "⚖️", "discover", {**POP}, 200, ["courtroom", "trial"]),
  ("survival",         Mv, "Survival Stories",             "🏔️", "discover", {**POP}, 300, ["survival"]),
  ("spy",              Mv, "Spies & Espionage",            "🕶️", "discover", {**POP}, 300, ["spy", "espionage"]),
  ("gangster",         Mv, "Gangster Epics",               "🎩", "discover", {**POP}, 300, ["gangster", "mafia"]),
  ("disaster",         Mv, "Disaster Movies",              "🌋", "discover", {**POP}, 200, ["disaster", "natural disaster"]),
  ("sports-movies",    Mv, "Sports Movies",                "🏏", "discover", {**POP}, 300, ["sports", "underdog"]),
  ("road-trip",        Mv, "Road Trips",                   "🚗", "discover", {**POP}, 200, ["road trip", "road movie"]),
  ("vampires",         Mv, "Vampires & Werewolves",        "🧛", "discover", {**POP}, 200, ["vampire", "werewolf"]),
  ("haunted",          Mv, "Haunted Houses",               "🏚️", "discover", {**POP}, 200, ["haunted house", "ghost"]),
  ("slashers",         Mv, "Slashers",                     "🎃", "discover", {**POP}, 200, ["slasher"]),
  ("found-footage",    Mv, "Found Footage",                "📹", "discover", {**POP}, 150, ["found footage"]),
  ("aliens",           Mv, "Alien Invasion",               "👽", "discover", {**POP}, 200, ["alien", "alien invasion"]),
  ("ai-robots",        Mv, "AI & Robots",                  "🤖", "discover", {**POP}, 200, ["artificial intelligence", "robot"]),
  ("christmas",        Mv, "Christmas & New Year",         "🎄", "discover", {**POP}, 300, ["christmas", "new year's eve", "holiday"]),
  ("kids-tv",          T,  "Kids & Family Series",         "🧒", "discover", {**POP, "with_genres": "10762|10751"}, 300),
  ("cartoons",         T,  "Cartoons (Non-Anime)",         "🐭", "discover", {**POP, "with_genres": "16", "without_original_language": "ja"}, 400),

  # ---------------- 18+ / not safe to watch (mainstream rated titles only, no adult/porn)
  ("nsfw-r-all",       Mv, "18+ · Every R-Rated Movie",    "🔞", "discover", {**POP, "certification_country": "US", "certification": "R", "vote_count.gte": 100}, 5000),
  ("nsfw-nc17",        Mv, "18+ · NC-17 & Uncut",          "⛔", "discover", {**POP, "certification_country": "US", "certification": "NC-17"}, 300),
  ("nsfw-erotic",      Mv, "18+ · Erotic Thrillers",       "💋", "discover", {**POP}, 400, ["erotic thriller", "erotic movie", "sensuality"]),
  ("nsfw-nudity-mov",  Mv, "18+ · Steamy & Explicit Movies","🌶️", "discover", {**POP, "vote_count.gte": 100}, 1000, ["nudity", "sex scene", "female nudity"]),
  ("nsfw-nudity-tv",   T,  "18+ · Steamy & Explicit Series","🌶️", "discover", {**POP}, 500, ["nudity", "sex scene", "female nudity"]),
  ("nsfw-gore",        Mv, "18+ · Gore & Extreme Horror",  "🩸", "discover", {**POP}, 500, ["gore", "splatter", "body horror", "torture"]),
  ("nsfw-violent",     Mv, "18+ · Brutal & Ultra-Violent", "🪓", "discover", {**POP, "vote_count.gte": 100}, 800, ["violence", "brutality", "bloodbath", "extreme violence"]),
  ("nsfw-violent-tv",  T,  "18+ · Brutal & Violent Series","🪓", "discover", {**POP}, 500, ["violence", "brutality", "graphic violence"]),
  ("nsfw-drugs",       Mv, "18+ · Drugs & Excess",         "💊", "discover", {**POP}, 300, ["drug addiction", "drugs", "cocaine"]),
  ("nsfw-dark-psych",  Mv, "18+ · Disturbing & Dark",      "🕳️", "discover", {**POP}, 300, ["psychopath", "disturbing", "cannibalism"]),
  ("nsfw-ml-a",        Mv, "18+ · Indian A-Rated",         "🅰️", "discover", {**POP, "certification_country": "IN", "certification": "A"}, 800),
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

PEOPLE = {}
def person_id(spec):
    """'Name' or 'Name:Alias'. Picks the best-known matching person."""
    if spec not in PEOPLE:
        names = spec.split(":")
        res = get("search/person", {"query": names[0]}).get("results") or []
        ok = [r for r in res if r.get("name", "").lower() in [n.lower() for n in names]] or res
        ok.sort(key=lambda r: -(r.get("popularity") or 0))
        PEOPLE[spec] = str(ok[0]["id"]) if ok else ""
    return PEOPLE[spec]

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
    with cf.ThreadPoolExecutor(16) as ex:
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
    cast = p.pop("_cast", None)
    if cast:
        pid = person_id(cast)
        if not pid:
            print(f"  skip {cid}: person not found {cast}")
            return []
        p["with_cast"] = pid
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
            vc = x.get("vote_count") or 0
            w = 1.0 / (1 + rank * 0.15) * (0.5 + (x.get("vote_average") or 0) / 20) * min(1.0, 0.25 + math.log10(vc + 1) / 4)
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

def build_legacy(get_fn, cache_dict, genres):
    """Returns [(cid, typ, display_name, metas)] for the v3 shelves. Shares v4's client and caches."""
    global get, CACHE_D
    get = get_fn; CACHE_D = cache_dict; GENRES.update(genres)
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
        if cid == "nsfw-r-all":
            order.append(("after-dark-series", T, fancy("After Dark · 18+ Series", "🔞")))

    typ_of = {cid: typ for cid, typ, _ in order}
    imdb_ids({f"{tt(typ_of[cid])}:{r['id']}" for cid, items in raw.items() for r, _ in items})
    out = []
    for cid, typ, name in order:
        metas, seen = [], set()
        for r, why in raw.get(cid, []):
            m = to_meta(r, typ, why)
            if m and m["id"] not in seen:
                seen.add(m["id"]); metas.append(m)
        out.append((cid, typ, name, metas))
    return out
