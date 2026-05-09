from app import db
from datetime import datetime

# Many-to-many join table
movie_genres = db.Table(
    'movie_genres',
    db.Column('movie_id', db.Integer, db.ForeignKey('movies.id',  ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id',  ondelete='CASCADE'), primary_key=True),
)


class Genre(db.Model):
    __tablename__ = 'genres'

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    icon = db.Column(db.String(10))

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'slug': self.slug, 'icon': self.icon}


class Movie(db.Model):
    __tablename__ = 'movies'

    id             = db.Column(db.Integer, primary_key=True)
    tmdb_id        = db.Column(db.Integer, unique=True)
    imdb_id        = db.Column(db.String(20), unique=True)
    title          = db.Column(db.String(255), nullable=False)
    original_title = db.Column(db.String(255))
    overview       = db.Column(db.Text)
    tagline        = db.Column(db.String(500))
    poster_url     = db.Column(db.String(500))
    backdrop_url   = db.Column(db.String(500))
    trailer_key    = db.Column(db.String(100))
    release_date   = db.Column(db.Date)
    runtime        = db.Column(db.Integer)
    language       = db.Column(db.String(10), default='en')
    status         = db.Column(db.String(30), default='Released')
    budget         = db.Column(db.BigInteger, default=0)
    revenue        = db.Column(db.BigInteger, default=0)
    popularity     = db.Column(db.Float, default=0)
    vote_average   = db.Column(db.Float, default=0)
    vote_count     = db.Column(db.Integer, default=0)
    adult          = db.Column(db.Boolean, default=False)
    director       = db.Column(db.String(100))
    cast_list      = db.Column(db.JSON)
    keywords       = db.Column(db.JSON)
    content_vector = db.Column(db.JSON)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    genres  = db.relationship('Genre', secondary=movie_genres, backref=db.backref('movies', lazy='dynamic'))
    ratings = db.relationship('Rating',  backref='movie', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('Review',  backref='movie', lazy='dynamic', cascade='all, delete-orphan')

    def avg_user_rating(self):
        from sqlalchemy import func
        from app.models.rating import Rating
        result = db.session.query(func.avg(Rating.score)).filter(Rating.movie_id == self.id).scalar()
        return round(float(result), 1) if result else None

    def to_dict(self, detailed=False):
        data = {
            'id':           self.id,
            'tmdb_id':      self.tmdb_id,
            'imdb_id':      self.imdb_id,
            'title':        self.title,
            'poster_url':   self.poster_url or '/assets/images/no-poster.jpg',
            'backdrop_url': self.backdrop_url,
            'release_date': self.release_date.isoformat() if self.release_date else None,
            'release_year': self.release_date.year if self.release_date else None,
            'runtime':      self.runtime,
            'vote_average': self.vote_average,
            'vote_count':   self.vote_count,
            'popularity':   self.popularity,
            'genres':       [g.to_dict() for g in self.genres],
            'trailer_key':  self.trailer_key,
        }
        if detailed:
            data.update({
                'overview':       self.overview,
                'tagline':        self.tagline,
                'original_title': self.original_title,
                'language':       self.language,
                'director':       self.director,
                'cast_list':      self.cast_list or [],
                'keywords':       self.keywords or [],
                'budget':         self.budget,
                'revenue':        self.revenue,
                'status':         self.status,
                'user_rating':    self.avg_user_rating(),
            })
        return data

    def __repr__(self):
        return f'<Movie {self.title}>'
