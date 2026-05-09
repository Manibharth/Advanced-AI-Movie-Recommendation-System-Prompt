"""
AI Recommendation Engine
Implements:
  - Content-based filtering (TF-IDF on title+overview+keywords+genres)
  - Collaborative filtering (user-item matrix cosine similarity)
  - Hybrid scoring with configurable weights
  - Mood-based recommendations
  - Trending / underrated / genre-specific modes
"""

from __future__ import annotations
import math
import json
import re
from collections import defaultdict
from typing import List, Dict, Any

from app import db, cache
from app.models.movie import Movie, Genre
from app.models.rating import Rating
from app.models.watchlist import Watchlist
from app.models.recommendation import RecommendationHistory


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cosine(vec_a: Dict, vec_b: Dict) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    dot   = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in vec_a)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _tokenize(text: str) -> List[str]:
    """Lowercase alphabetical tokens, at least 3 chars."""
    return [w for w in re.findall(r'[a-z]+', text.lower()) if len(w) >= 3]


def _tfidf_vector(doc: str, idf: Dict[str, float]) -> Dict[str, float]:
    tokens = _tokenize(doc)
    if not tokens:
        return {}
    tf: Dict[str, float] = defaultdict(float)
    for t in tokens:
        tf[t] += 1
    for t in tf:
        tf[t] = (tf[t] / len(tokens)) * idf.get(t, 1.0)
    return dict(tf)


# ── Main Class ────────────────────────────────────────────────────────────────

class AIRecommender:

    MOOD_GENRES = {
        'excited':    ['action', 'adventure', 'superhero'],
        'relaxed':    ['comedy', 'romance', 'animation'],
        'curious':    ['sci-fi', 'mystery', 'documentary'],
        'sad':        ['drama', 'romance'],
        'scared':     ['horror', 'thriller'],
        'thoughtful': ['drama', 'documentary', 'war'],
        'happy':      ['comedy', 'animation', 'romance'],
        'bored':      ['action', 'thriller', 'mystery'],
    }

    REC_MODES = {
        'netflix':     'Top Picks For You',
        'because':     'Because You Watched',
        'trending':    'Trending Now',
        'mindblowing': 'Mind-Blowing Movies',
        'anime':       'Anime Recommendations',
        'underrated':  'Underrated Gems',
        'weekend':     'Weekend Binge',
        'scifi':       'Sci-Fi Universe',
        'horror':      'Horror Night',
        'mood':        'Mood-Based Picks',
    }

    # ── IDF Cache ─────────────────────────────────────────────

    def _get_idf(self) -> Dict[str, float]:
        cached = cache.get('idf_corpus')
        if cached:
            return cached

        movies = Movie.query.with_entities(Movie.title, Movie.overview, Movie.keywords).all()
        df: Dict[str, int] = defaultdict(int)
        N = len(movies) or 1
        for m in movies:
            text = f"{m.title or ''} {m.overview or ''} {json.dumps(m.keywords or [])}"
            for t in set(_tokenize(text)):
                df[t] += 1
        idf = {t: math.log(N / (freq + 1)) + 1 for t, freq in df.items()}
        cache.set('idf_corpus', idf, timeout=3600)
        return idf

    # ── Content Vector ────────────────────────────────────────

    def _movie_vector(self, movie: Movie, idf: Dict[str, float]) -> Dict[str, float]:
        text = (
            f"{movie.title or ''} {movie.overview or ''} "
            f"{json.dumps(movie.keywords or [])} "
            f"{movie.director or ''} "
            f"{' '.join(g.name for g in movie.genres)}"
        )
        vec = _tfidf_vector(text, idf)
        # Boost by genre slugs so genre similarity is weighted
        for g in movie.genres:
            vec[f'genre_{g.slug}'] = vec.get(f'genre_{g.slug}', 0) + 2.0
        return vec

    # ── Collaborative Filtering ───────────────────────────────

    def _collaborative_scores(self, user_id: int, candidate_ids: List[int]) -> Dict[int, float]:
        """Item-based CF: find users who rated similar movies and aggregate."""
        # Get movies this user has rated
        my_ratings: List[Rating] = (Rating.query.filter_by(user_id=user_id)
                                     .with_entities(Rating.movie_id, Rating.score).all())
        if not my_ratings:
            return {}

        my_movie_ids = {r.movie_id for r in my_ratings}
        my_score_map = {r.movie_id: r.score / 10.0 for r in my_ratings}

        # Find other users who rated overlapping movies
        similar_users: List[Rating] = (
            Rating.query
            .filter(Rating.movie_id.in_(my_movie_ids))
            .filter(Rating.user_id != user_id)
            .all()
        )
        if not similar_users:
            return {}

        # Group ratings by user
        user_ratings: Dict[int, Dict[int, float]] = defaultdict(dict)
        for r in similar_users:
            user_ratings[r.user_id][r.movie_id] = r.score / 10.0

        # Compute similarity between current user and each other user
        user_sim: Dict[int, float] = {}
        for uid, ratings in user_ratings.items():
            shared = set(ratings) & my_movie_ids
            if len(shared) < 2:
                continue
            va = {mid: my_score_map[mid] for mid in shared}
            vb = {mid: ratings[mid]      for mid in shared}
            user_sim[uid] = _cosine(va, vb)

        if not user_sim:
            return {}

        # Aggregate scores for candidate movies
        scores: Dict[int, float] = defaultdict(float)
        weights: Dict[int, float] = defaultdict(float)
        for uid, sim in user_sim.items():
            if sim < 0.1:
                continue
            for rating in Rating.query.filter_by(user_id=uid).all():
                if rating.movie_id in candidate_ids:
                    scores[rating.movie_id]  += sim * (rating.score / 10.0)
                    weights[rating.movie_id] += sim

        return {mid: scores[mid] / weights[mid] for mid in scores if weights[mid] > 0}

    # ── Public API ────────────────────────────────────────────

    def get_recommendations(
        self,
        user_id: int,
        mode: str = 'netflix',
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return a scored list of movie dicts for the given mode."""

        user_prefs: dict = {}
        from app.models.user import User
        user = User.query.get(user_id)
        if user:
            user_prefs = user.get_preferences()

        if mode == 'trending':
            return self._trending(limit)
        if mode == 'underrated':
            return self._underrated(limit)
        if mode == 'anime':
            return self._by_genre('anime', limit)
        if mode == 'scifi':
            return self._by_genre('sci-fi', limit)
        if mode == 'horror':
            return self._by_genre('horror', limit)
        if mode == 'weekend':
            return self._weekend_binge(limit)
        if mode == 'mindblowing':
            return self._mindblowing(limit)
        if mode == 'mood':
            mood = user_prefs.get('mood', 'excited')
            return self._mood_based(mood, limit)
        if mode == 'because':
            return self._because_you_watched(user_id, limit)

        # Default: hybrid personalised
        return self._hybrid(user_id, user_prefs, limit)

    def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        target = Movie.query.get(movie_id)
        if not target:
            return []

        idf  = self._get_idf()
        t_vec = self._movie_vector(target, idf)
        all_movies = Movie.query.filter(Movie.id != movie_id).all()

        scored = []
        for m in all_movies:
            m_vec = self._movie_vector(m, idf)
            sim   = _cosine(t_vec, m_vec)
            if sim > 0:
                d = m.to_dict()
                d['similarity_score'] = round(sim, 4)
                scored.append(d)

        scored.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored[:limit]

    def log_recommendation(
        self, user_id: int, movie_id: int,
        rec_type: str, confidence: float, reason: str = ''
    ):
        entry = RecommendationHistory(
            user_id=user_id, movie_id=movie_id,
            rec_type=rec_type, confidence=confidence, reason=reason,
        )
        db.session.add(entry)
        db.session.commit()

    # ── Private Modes ─────────────────────────────────────────

    def _hybrid(self, user_id: int, prefs: dict, limit: int) -> List[Dict]:
        idf = self._get_idf()

        # Already seen / rated / watchlisted
        rated_ids = {r.movie_id for r in Rating.query.filter_by(user_id=user_id).all()}
        watchlist_ids = {w.movie_id for w in Watchlist.query.filter_by(user_id=user_id).all()}
        seen_ids = rated_ids | watchlist_ids

        candidates = Movie.query.filter(Movie.id.notin_(seen_ids) if seen_ids else True).all()
        if not candidates:
            candidates = Movie.query.order_by(Movie.popularity.desc()).limit(50).all()

        candidate_ids = [m.id for m in candidates]

        # Content-based
        fav_genres   = prefs.get('favorite_genres', [])
        genre_movies = (Rating.query.filter_by(user_id=user_id)
                        .filter(Rating.score >= 7).all())
        if genre_movies:
            ref_movies = [Movie.query.get(r.movie_id) for r in genre_movies[:5]]
            ref_movies = [m for m in ref_movies if m]
        else:
            ref_movies = []

        content_scores: Dict[int, float] = {}
        if ref_movies:
            for ref in ref_movies:
                ref_vec = self._movie_vector(ref, idf)
                for cand in candidates:
                    cand_vec = self._movie_vector(cand, idf)
                    sim      = _cosine(ref_vec, cand_vec)
                    content_scores[cand.id] = max(content_scores.get(cand.id, 0), sim)

        # Collaborative
        collab_scores = self._collaborative_scores(user_id, candidate_ids)

        # Combine
        w_content, w_collab, w_pop = 0.5, 0.3, 0.2
        scored = []
        max_pop = max((m.popularity for m in candidates), default=1) or 1

        for m in candidates:
            cb  = content_scores.get(m.id, 0)
            cf  = collab_scores.get(m.id, 0)
            pop = m.popularity / max_pop
            # Genre bonus
            genre_bonus = 0.1 if any(g.id in fav_genres for g in m.genres) else 0
            score = w_content * cb + w_collab * cf + w_pop * pop + genre_bonus
            d = m.to_dict()
            d['recommendation_score'] = round(score, 4)
            d['recommendation_type']  = 'Top Picks For You'
            scored.append(d)

        scored.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return scored[:limit]

    def _trending(self, limit: int) -> List[Dict]:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=90)).date()
        movies = (Movie.query
                  .filter(Movie.release_date >= cutoff)
                  .order_by(Movie.popularity.desc())
                  .limit(limit * 2).all())
        if len(movies) < limit:
            movies = Movie.query.order_by(Movie.popularity.desc()).limit(limit).all()
        result = []
        for m in movies[:limit]:
            d = m.to_dict()
            d['recommendation_type'] = 'Trending Now'
            result.append(d)
        return result

    def _underrated(self, limit: int) -> List[Dict]:
        # High user rating but low popularity → underrated
        movies = (Movie.query
                  .filter(Movie.vote_average >= 7.5)
                  .filter(Movie.popularity < 50)
                  .order_by((Movie.vote_average - Movie.popularity / 100).desc())
                  .limit(limit).all())
        result = []
        for m in movies:
            d = m.to_dict()
            d['recommendation_type'] = 'Underrated Gems'
            result.append(d)
        return result

    def _by_genre(self, genre_slug: str, limit: int) -> List[Dict]:
        genre = Genre.query.filter_by(slug=genre_slug).first()
        label = self.REC_MODES.get(genre_slug.replace('-', ''), genre_slug.title())
        if not genre:
            return []
        movies = (Movie.query.join(Movie.genres)
                  .filter(Genre.id == genre.id)
                  .order_by(Movie.vote_average.desc())
                  .limit(limit).all())
        result = []
        for m in movies:
            d = m.to_dict()
            d['recommendation_type'] = label
            result.append(d)
        return result

    def _weekend_binge(self, limit: int) -> List[Dict]:
        # Mid-length movies with high ratings — good for a binge
        movies = (Movie.query
                  .filter(Movie.runtime.between(85, 130))
                  .filter(Movie.vote_average >= 7.0)
                  .order_by(Movie.vote_average.desc())
                  .limit(limit).all())
        result = []
        for m in movies:
            d = m.to_dict()
            d['recommendation_type'] = 'Weekend Binge'
            result.append(d)
        return result

    def _mindblowing(self, limit: int) -> List[Dict]:
        # High rating + high vote count → universally loved mind-benders
        movies = (Movie.query
                  .filter(Movie.vote_average >= 8.0)
                  .filter(Movie.vote_count >= 5000)
                  .order_by((Movie.vote_average * Movie.vote_count).desc())
                  .limit(limit).all())
        result = []
        for m in movies:
            d = m.to_dict()
            d['recommendation_type'] = 'Mind-Blowing Movies'
            result.append(d)
        return result

    def _mood_based(self, mood: str, limit: int) -> List[Dict]:
        genre_slugs = self.MOOD_GENRES.get(mood, ['action', 'drama'])
        genres = Genre.query.filter(Genre.slug.in_(genre_slugs)).all()
        genre_ids = [g.id for g in genres]
        movies = (Movie.query.join(Movie.genres)
                  .filter(Genre.id.in_(genre_ids))
                  .order_by(Movie.vote_average.desc())
                  .limit(limit).all())
        result = []
        for m in movies:
            d = m.to_dict()
            d['recommendation_type'] = f'Mood: {mood.title()}'
            result.append(d)
        return result

    def _because_you_watched(self, user_id: int, limit: int) -> List[Dict]:
        # Find the most recently rated/watched movie and get similars
        last = (Rating.query.filter_by(user_id=user_id)
                .order_by(Rating.created_at.desc()).first())
        if not last:
            return self._trending(limit)
        movie = Movie.query.get(last.movie_id)
        if not movie:
            return self._trending(limit)
        similars = self.get_similar_movies(last.movie_id, limit)
        for d in similars:
            d['recommendation_type'] = f'Because you watched {movie.title}'
        return similars

    # ── Chatbot AI Suggestions ────────────────────────────────

    def chatbot_suggest(self, query: str, user_id: int = None) -> Dict[str, Any]:
        """Rule-based + keyword chatbot movie suggestions."""
        q = query.lower()
        suggestions = []
        message = ''

        # Detect mood/genre keywords
        mood_keywords = {
            'sad': 'drama', 'cry': 'drama', 'happy': 'comedy', 'fun': 'comedy',
            'scary': 'horror', 'horror': 'horror', 'action': 'action',
            'adventure': 'adventure', 'romance': 'romance', 'love': 'romance',
            'space': 'sci-fi', 'future': 'sci-fi', 'anime': 'anime',
            'animated': 'animation', 'cartoon': 'animation', 'mystery': 'mystery',
            'thriller': 'thriller', 'suspense': 'thriller',
        }

        detected_genre = None
        for kw, genre in mood_keywords.items():
            if kw in q:
                detected_genre = genre
                break

        if detected_genre:
            suggestions = self._by_genre(detected_genre, 5)
            message = f"Here are some great {detected_genre} picks for you! 🎬"
        elif 'trending' in q or 'popular' in q or 'new' in q:
            suggestions = self._trending(5)
            message = "Here are the hottest movies right now! 🔥"
        elif 'underrated' in q or 'hidden' in q or 'gem' in q:
            suggestions = self._underrated(5)
            message = "Here are some underrated gems you might have missed! 💎"
        elif 'top' in q or 'best' in q or 'greatest' in q:
            suggestions = self._mindblowing(5)
            message = "Here are some of the greatest movies of all time! 🏆"
        elif 'weekend' in q or 'binge' in q:
            suggestions = self._weekend_binge(5)
            message = "Perfect weekend binge picks! 🍿"
        else:
            # Generic search on movie titles
            from sqlalchemy import or_
            words = [w for w in q.split() if len(w) > 3]
            if words:
                filters = [Movie.title.ilike(f'%{w}%') for w in words]
                found = Movie.query.filter(or_(*filters)).limit(5).all()
                suggestions = [m.to_dict() for m in found]
                message = f"Found {len(suggestions)} movies matching your query!"
            if not suggestions:
                if user_id:
                    suggestions = self._hybrid(user_id, {}, 5)
                else:
                    suggestions = self._trending(5)
                message = "Here are some movies I think you'll enjoy! 🎥"

        return {'message': message, 'suggestions': suggestions[:5]}
