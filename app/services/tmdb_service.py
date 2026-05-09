"""
TMDB API Integration Service
Handles all communication with The Movie Database (TMDB) API v3.
Provides functions to fetch movie details, credits, videos, and keywords,
and to keep the local Movie table in sync with TMDB data.
"""

import os
import logging
from datetime import datetime, date

import requests

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

TMDB_BASE_URL   = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/original"

# Mapping from TMDB genre IDs to the genre names used in our DB.
# TMDB's full genre list as of 2024 (movies endpoint).
TMDB_GENRE_MAP: dict[int, str] = {
    28:    "Action",
    12:    "Adventure",
    16:    "Animation",
    35:    "Comedy",
    80:    "Crime",
    99:    "Documentary",
    18:    "Drama",
    10751: "Family",
    14:    "Fantasy",
    36:    "History",
    27:    "Horror",
    10402: "Music",
    9648:  "Mystery",
    10749: "Romance",
    878:   "Science Fiction",
    10770: "TV Movie",
    53:    "Thriller",
    10752: "War",
    37:    "Western",
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _api_key() -> str | None:
    """Return the TMDB API key from the environment, or None if unset."""
    key = os.environ.get("TMDB_API_KEY", "").strip()
    return key if key else None


def _get(endpoint: str, params: dict | None = None, timeout: int = 10) -> dict | None:
    """
    Perform a GET request against the TMDB API.

    Returns the parsed JSON dict on success, or None on any error
    (missing key, network failure, non-200 status).
    """
    key = _api_key()
    if not key:
        logger.warning("TMDB_API_KEY is not set – skipping TMDB request.")
        return None

    url = f"{TMDB_BASE_URL}/{endpoint.lstrip('/')}"
    merged_params = {"api_key": key, "language": "en-US"}
    if params:
        merged_params.update(params)

    try:
        resp = requests.get(url, params=merged_params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.error("TMDB %s returned HTTP %s: %s", url, resp.status_code, resp.text[:200])
        return None
    except requests.RequestException as exc:
        logger.error("TMDB request failed for %s: %s", url, exc)
        return None


def _parse_release_date(raw: str | None) -> date | None:
    """Parse a 'YYYY-MM-DD' string into a Python date, or return None."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_poster_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{POSTER_BASE_URL}{path}"


def _build_backdrop_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{BACKDROP_BASE_URL}{path}"


# ── Core fetch functions ─────────────────────────────────────────────────────

def fetch_movie_details(tmdb_id: int) -> dict | None:
    """
    Return a fully normalised dict ready to be applied to a Movie model instance.

    Keys returned:
        tmdb_id, imdb_id, title, original_title, tagline, overview,
        poster_url, backdrop_url, trailer_key, release_date, runtime,
        language, status, budget, revenue, adult,
        vote_average, vote_count, popularity,
        director, cast_list, keywords, genres (list of TMDB genre name strings)

    Returns None if the API key is missing or the request fails.
    """
    if not _api_key():
        return None

    # 1. Core details
    details = _get(f"movie/{tmdb_id}")
    if not details:
        return None

    # 2. Credits
    credits_data = _get(f"movie/{tmdb_id}/credits") or {}
    crew = credits_data.get("crew", [])
    cast = credits_data.get("cast", [])

    director = next(
        (member["name"] for member in crew if member.get("job") == "Director"),
        None,
    )
    cast_list = [
        {
            "name":       member["name"],
            "character":  member.get("character", ""),
            "profile_url": (
                _build_poster_url(member["profile_path"])
                if member.get("profile_path")
                else None
            ),
            "order": member.get("order", idx),
        }
        for idx, member in enumerate(cast[:5])
    ]

    # 3. Videos – find first YouTube trailer
    videos_data = _get(f"movie/{tmdb_id}/videos") or {}
    trailer_key = None
    for video in videos_data.get("results", []):
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            trailer_key = video.get("key")
            break
    # Fallback: any YouTube teaser if no trailer found
    if not trailer_key:
        for video in videos_data.get("results", []):
            if video.get("site") == "YouTube":
                trailer_key = video.get("key")
                break

    # 4. Keywords
    keywords_data = _get(f"movie/{tmdb_id}/keywords") or {}
    keywords = [kw["name"] for kw in keywords_data.get("keywords", [])]

    # 5. Genre names from TMDB genre IDs
    genre_names = [
        TMDB_GENRE_MAP[g["id"]]
        for g in details.get("genres", [])
        if g["id"] in TMDB_GENRE_MAP
    ]

    return {
        "tmdb_id":        tmdb_id,
        "imdb_id":        details.get("imdb_id") or None,
        "title":          details.get("title", ""),
        "original_title": details.get("original_title") or details.get("title", ""),
        "tagline":        details.get("tagline") or None,
        "overview":       details.get("overview") or None,
        "poster_url":     _build_poster_url(details.get("poster_path")),
        "backdrop_url":   _build_backdrop_url(details.get("backdrop_path")),
        "trailer_key":    trailer_key,
        "release_date":   _parse_release_date(details.get("release_date")),
        "runtime":        details.get("runtime") or None,
        "language":       details.get("original_language", "en"),
        "status":         details.get("status", "Released"),
        "budget":         details.get("budget", 0),
        "revenue":        details.get("revenue", 0),
        "adult":          bool(details.get("adult", False)),
        "vote_average":   float(details.get("vote_average", 0)),
        "vote_count":     int(details.get("vote_count", 0)),
        "popularity":     float(details.get("popularity", 0)),
        "director":       director,
        "cast_list":      cast_list,
        "keywords":       keywords,
        "genres":         genre_names,   # list of name strings
    }


# ── DB sync helpers ───────────────────────────────────────────────────────────

def _apply_tmdb_data_to_movie(movie, data: dict) -> None:
    """
    Write normalised TMDB data onto a Movie ORM instance.
    Resolves genre names to Genre ORM objects and updates the relationship.
    Does NOT commit – caller is responsible for db.session.commit().
    """
    from app.models.movie import Genre

    scalar_fields = [
        "tmdb_id", "imdb_id", "title", "original_title", "tagline", "overview",
        "poster_url", "backdrop_url", "trailer_key", "release_date", "runtime",
        "language", "status", "budget", "revenue", "adult",
        "vote_average", "vote_count", "popularity",
        "director", "cast_list", "keywords",
    ]
    for field in scalar_fields:
        if field in data and data[field] is not None:
            setattr(movie, field, data[field])

    # Resolve genre name strings to Genre ORM objects
    genre_names: list[str] = data.get("genres", [])
    if genre_names:
        genre_objs = Genre.query.filter(Genre.name.in_(genre_names)).all()
        movie.genres = genre_objs


def sync_all_movies() -> dict:
    """
    Iterate every Movie in the DB that has a tmdb_id and refresh its data
    from TMDB.

    Returns a summary dict: {'updated': N, 'failed': M, 'skipped': K}
    """
    from app import db
    from app.models.movie import Movie

    if not _api_key():
        logger.warning("sync_all_movies: TMDB_API_KEY not set, aborting.")
        return {"updated": 0, "failed": 0, "skipped": 0, "error": "TMDB_API_KEY not configured"}

    movies = Movie.query.filter(Movie.tmdb_id.isnot(None)).all()
    updated = failed = skipped = 0

    for movie in movies:
        try:
            data = fetch_movie_details(movie.tmdb_id)
            if data is None:
                failed += 1
                logger.error("Failed to fetch TMDB data for movie id=%s tmdb_id=%s", movie.id, movie.tmdb_id)
                continue
            _apply_tmdb_data_to_movie(movie, data)
            db.session.commit()
            updated += 1
            logger.info("Synced movie id=%s '%s'", movie.id, movie.title)
        except Exception as exc:
            db.session.rollback()
            failed += 1
            logger.exception("Error syncing movie id=%s: %s", movie.id, exc)

    logger.info("sync_all_movies complete: updated=%s failed=%s skipped=%s", updated, failed, skipped)
    return {"updated": updated, "failed": failed, "skipped": skipped}


def fetch_popular_movies(pages: int = 3) -> dict:
    """
    Fetch the top `pages` pages of TMDB popular movies and upsert any that
    are not already in our DB (matched by tmdb_id).

    Returns a summary dict: {'added': N, 'skipped': M, 'failed': K}
    """
    from app import db
    from app.models.movie import Movie

    if not _api_key():
        logger.warning("fetch_popular_movies: TMDB_API_KEY not set, aborting.")
        return {"added": 0, "skipped": 0, "failed": 0, "error": "TMDB_API_KEY not configured"}

    added = skipped = failed = 0

    for page_num in range(1, pages + 1):
        page_data = _get("movie/popular", params={"page": page_num})
        if not page_data:
            logger.error("fetch_popular_movies: failed to fetch page %s", page_num)
            failed += 1
            continue

        results = page_data.get("results", [])
        logger.info("fetch_popular_movies: page %s/%s – %s results", page_num, pages, len(results))

        for item in results:
            tmdb_id = item.get("id")
            if not tmdb_id:
                continue

            # Skip if already in DB
            existing = Movie.query.filter_by(tmdb_id=tmdb_id).first()
            if existing:
                skipped += 1
                continue

            try:
                data = fetch_movie_details(tmdb_id)
                if data is None:
                    failed += 1
                    logger.error("fetch_popular_movies: could not fetch details for tmdb_id=%s", tmdb_id)
                    continue

                movie = Movie(title=data["title"])
                _apply_tmdb_data_to_movie(movie, data)
                db.session.add(movie)
                db.session.commit()
                added += 1
                logger.info("Added new movie '%s' (tmdb_id=%s)", data["title"], tmdb_id)
            except Exception as exc:
                db.session.rollback()
                failed += 1
                logger.exception("fetch_popular_movies: error adding tmdb_id=%s: %s", tmdb_id, exc)

    logger.info("fetch_popular_movies complete: added=%s skipped=%s failed=%s", added, skipped, failed)
    return {"added": added, "skipped": skipped, "failed": failed}
