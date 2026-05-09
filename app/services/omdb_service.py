"""
OMDb API Integration Service
Uses the Open Movie Database API (omdbapi.com) to fetch movie data.
Free tier: 1,000 requests/day. Sign up at omdbapi.com to get a key.
"""

import os
import logging
from datetime import datetime, date

import requests

logger = logging.getLogger(__name__)

OMDB_BASE_URL = "http://www.omdbapi.com/"

# 60 popular movies by IMDb ID used for the "fetch popular" feature
POPULAR_IMDB_IDS = [
    "tt0111161",  # The Shawshank Redemption
    "tt0068646",  # The Godfather
    "tt0468569",  # The Dark Knight
    "tt0071562",  # The Godfather Part II
    "tt0050083",  # 12 Angry Men
    "tt0108052",  # Schindler's List
    "tt0167260",  # The Lord of the Rings: The Return of the King
    "tt0110912",  # Pulp Fiction
    "tt0060196",  # The Good, the Bad and the Ugly
    "tt0137523",  # Fight Club
    "tt0120737",  # The Lord of the Rings: The Fellowship of the Ring
    "tt0109830",  # Forrest Gump
    "tt1375666",  # Inception
    "tt0167261",  # The Lord of the Rings: The Two Towers
    "tt0080684",  # Star Wars: The Empire Strikes Back
    "tt0133093",  # The Matrix
    "tt0073486",  # One Flew Over the Cuckoo's Nest
    "tt0099685",  # Goodfellas
    "tt0047478",  # Seven Samurai
    "tt0114369",  # Se7en
    "tt0317248",  # City of God
    "tt0102926",  # The Silence of the Lambs
    "tt0076759",  # Star Wars: A New Hope
    "tt0038650",  # It's a Wonderful Life
    "tt0245429",  # Spirited Away
    "tt0120815",  # Saving Private Ryan
    "tt0120689",  # The Green Mile
    "tt0816692",  # Interstellar
    "tt0056058",  # Harakiri
    "tt0114814",  # The Usual Suspects
    "tt0034583",  # Casablanca
    "tt0054215",  # Psycho
    "tt0027977",  # Modern Times
    "tt0120586",  # American History X
    "tt0021749",  # City Lights
    "tt0253474",  # The Pianist
    "tt0407887",  # The Departed
    "tt0088763",  # Back to the Future
    "tt0103064",  # Terminator 2: Judgment Day
    "tt0110413",  # Léon: The Professional
    "tt0172495",  # Gladiator
    "tt0482571",  # The Prestige
    "tt1853728",  # Django Unchained
    "tt0364569",  # Oldboy
    "tt2582802",  # Whiplash
    "tt0119698",  # Princess Mononoke
    "tt0361748",  # Inglourious Basterds
    "tt0435761",  # Toy Story 3
    "tt1345836",  # The Dark Knight Rises
    "tt0118799",  # Life is Beautiful
    "tt0047396",  # Rear Window
    "tt0208092",  # Snatch
    "tt0055630",  # Yojimbo
    "tt0057012",  # Dr. Strangelove
    "tt0078788",  # Apocalypse Now
    "tt0081505",  # The Shining
    "tt0082971",  # Raiders of the Lost Ark
    "tt0986264",  # Taare Zameen Par
    "tt0266543",  # Finding Nemo
    "tt0910970",  # WALL·E
]


def _api_key() -> str | None:
    key = os.environ.get("OMDB_API_KEY", "").strip()
    return key if key else None


def _get(params: dict, timeout: int = 10) -> dict | None:
    key = _api_key()
    if not key:
        logger.warning("OMDB_API_KEY is not set – skipping OMDb request.")
        return None

    merged = {"apikey": key, "plot": "full", "r": "json"}
    merged.update(params)

    try:
        resp = requests.get(OMDB_BASE_URL, params=merged, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Response") == "True":
                return data
            logger.warning("OMDb returned error: %s", data.get("Error", "Unknown"))
            return None
        logger.error("OMDb returned HTTP %s", resp.status_code)
        return None
    except requests.RequestException as exc:
        logger.error("OMDb request failed: %s", exc)
        return None


def _parse_runtime(raw: str | None) -> int | None:
    """'152 min' → 152"""
    if not raw or raw == "N/A":
        return None
    try:
        return int(raw.replace(" min", "").strip())
    except ValueError:
        return None


def _parse_rating(raw: str | None) -> float:
    if not raw or raw == "N/A":
        return 0.0
    try:
        return round(float(raw), 1)
    except ValueError:
        return 0.0


def _parse_votes(raw: str | None) -> int:
    if not raw or raw == "N/A":
        return 0
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        return 0


def _parse_release_date(raw: str | None) -> date | None:
    if not raw or raw == "N/A":
        return None
    for fmt in ("%d %b %Y", "%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_poster(raw: str | None) -> str | None:
    if not raw or raw == "N/A":
        return None
    return raw


def _parse_genres(raw: str | None) -> list[str]:
    """'Action, Crime, Drama' → ['Action', 'Crime', 'Drama']"""
    if not raw or raw == "N/A":
        return []
    return [g.strip() for g in raw.split(",") if g.strip()]


def _parse_cast(raw: str | None) -> list[dict]:
    """'Christian Bale, Heath Ledger' → [{name: ..., character: '', order: N}]"""
    if not raw or raw == "N/A":
        return []
    return [
        {"name": n.strip(), "character": "", "profile_url": None, "order": i}
        for i, n in enumerate(raw.split(","))
        if n.strip()
    ]


def fetch_movie_details_by_imdb(imdb_id: str) -> dict | None:
    return _normalise(_get({"i": imdb_id}))


def fetch_movie_details_by_title(title: str, year: int | None = None) -> dict | None:
    params = {"t": title}
    if year:
        params["y"] = year
    return _normalise(_get(params))


def _normalise(data: dict | None) -> dict | None:
    if not data:
        return None
    return {
        "imdb_id":        data.get("imdbID") or None,
        "title":          data.get("Title", ""),
        "original_title": data.get("Title", ""),
        "tagline":        None,
        "overview":       data.get("Plot") if data.get("Plot") != "N/A" else None,
        "poster_url":     _parse_poster(data.get("Poster")),
        "backdrop_url":   None,
        "trailer_key":    None,
        "release_date":   _parse_release_date(data.get("Released") or data.get("Year")),
        "runtime":        _parse_runtime(data.get("Runtime")),
        "language":       (data.get("Language") or "en").split(",")[0].strip().lower()[:2],
        "status":         "Released",
        "budget":         0,
        "revenue":        0,
        "adult":          False,
        "vote_average":   _parse_rating(data.get("imdbRating")),
        "vote_count":     _parse_votes(data.get("imdbVotes")),
        "popularity":     _parse_votes(data.get("imdbVotes")) / 10000.0,
        "director":       data.get("Director") if data.get("Director") != "N/A" else None,
        "cast_list":      _parse_cast(data.get("Actors")),
        "keywords":       [],
        "genres":         _parse_genres(data.get("Genre")),
    }


# ── DB sync helpers ───────────────────────────────────────────────────────────

def _apply_omdb_data_to_movie(movie, data: dict) -> None:
    from app.models.movie import Genre

    scalar_fields = [
        "imdb_id", "title", "original_title", "tagline", "overview",
        "poster_url", "backdrop_url", "trailer_key", "release_date", "runtime",
        "language", "status", "budget", "revenue", "adult",
        "vote_average", "vote_count", "popularity",
        "director", "cast_list", "keywords",
    ]
    for field in scalar_fields:
        if field in data and data[field] is not None:
            setattr(movie, field, data[field])

    genre_names: list[str] = data.get("genres", [])
    if genre_names:
        from app import db
        import re
        with db.session.no_autoflush:
            genre_objs = Genre.query.filter(Genre.name.in_(genre_names)).all()
            existing_names = {g.name for g in genre_objs}
            for name in genre_names:
                if name not in existing_names:
                    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                    new_genre = Genre(name=name, slug=slug)
                    db.session.add(new_genre)
                    genre_objs.append(new_genre)
        movie.genres = genre_objs


def sync_all_movies() -> dict:
    """
    For every Movie in the DB, try to fetch updated data from OMDb.
    Matches by imdb_id first, then by title.
    Returns {'updated': N, 'failed': M, 'skipped': K}
    """
    from app import db
    from app.models.movie import Movie

    if not _api_key():
        return {"updated": 0, "failed": 0, "skipped": 0,
                "error": "OMDB_API_KEY not configured"}

    movies = Movie.query.all()
    updated = failed = skipped = 0

    for movie in movies:
        try:
            data = None
            if movie.imdb_id:
                data = fetch_movie_details_by_imdb(movie.imdb_id)
            if data is None:
                year = movie.release_date.year if movie.release_date else None
                data = fetch_movie_details_by_title(movie.title, year)
            if data is None:
                failed += 1
                logger.error("Could not fetch OMDb data for movie id=%s '%s'", movie.id, movie.title)
                continue
            _apply_omdb_data_to_movie(movie, data)
            db.session.commit()
            updated += 1
            logger.info("Synced movie id=%s '%s'", movie.id, movie.title)
        except Exception as exc:
            db.session.rollback()
            failed += 1
            logger.exception("Error syncing movie id=%s: %s", movie.id, exc)

    return {"updated": updated, "failed": failed, "skipped": skipped}


def fetch_popular_movies(pages: int = 3) -> dict:
    """
    Import popular movies from the curated IMDb ID list.
    `pages` maps to chunks of 20 IDs (max 3 pages = 60 movies).
    Returns {'added': N, 'skipped': M, 'failed': K}
    """
    from app import db
    from app.models.movie import Movie

    if not _api_key():
        return {"added": 0, "skipped": 0, "failed": 0,
                "error": "OMDB_API_KEY not configured"}

    per_page = 20
    end = min(pages * per_page, len(POPULAR_IMDB_IDS))
    ids_to_fetch = POPULAR_IMDB_IDS[:end]

    added = skipped = failed = 0

    for imdb_id in ids_to_fetch:
        existing = Movie.query.filter_by(imdb_id=imdb_id).first()
        if existing:
            skipped += 1
            continue
        try:
            data = fetch_movie_details_by_imdb(imdb_id)
            if data is None:
                failed += 1
                logger.error("Could not fetch OMDb data for imdb_id=%s", imdb_id)
                continue
            movie = Movie(title=data["title"])
            _apply_omdb_data_to_movie(movie, data)
            db.session.add(movie)
            db.session.commit()
            added += 1
            logger.info("Added movie '%s' (imdb_id=%s)", data["title"], imdb_id)
        except Exception as exc:
            db.session.rollback()
            failed += 1
            logger.exception("Error adding imdb_id=%s: %s", imdb_id, exc)

    return {"added": added, "skipped": skipped, "failed": failed}
