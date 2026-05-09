from app.models.user         import User
from app.models.movie        import Movie, Genre, movie_genres
from app.models.rating       import Rating, Review
from app.models.watchlist    import Watchlist
from app.models.recommendation import RecommendationHistory, AIFeedback
from app.models.search       import SearchHistory

__all__ = [
    'User', 'Movie', 'Genre', 'movie_genres',
    'Rating', 'Review', 'Watchlist',
    'RecommendationHistory', 'AIFeedback', 'SearchHistory',
]
