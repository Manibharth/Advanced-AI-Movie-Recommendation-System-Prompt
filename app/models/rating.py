from app import db
from datetime import datetime


class Rating(db.Model):
    __tablename__ = 'ratings'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id',  ondelete='CASCADE'), nullable=False)
    movie_id   = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False)
    score      = db.Column(db.SmallInteger, nullable=False)
    liked      = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id', name='uq_rating'),)

    def to_dict(self):
        return {
            'id':       self.id,
            'user_id':  self.user_id,
            'movie_id': self.movie_id,
            'score':    self.score,
            'liked':    self.liked,
            'created_at': self.created_at.isoformat(),
        }


class Review(db.Model):
    __tablename__ = 'reviews'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id',  ondelete='CASCADE'), nullable=False)
    movie_id   = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    sentiment  = db.Column(db.Enum('positive', 'neutral', 'negative'), default='neutral')
    score      = db.Column(db.Float)
    spoiler    = db.Column(db.Boolean, default=False)
    likes      = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':        self.id,
            'user_id':   self.user_id,
            'username':  self.user.username if self.user else None,
            'avatar':    self.user.avatar_url if self.user else None,
            'movie_id':  self.movie_id,
            'content':   self.content,
            'sentiment': self.sentiment,
            'score':     self.score,
            'spoiler':   self.spoiler,
            'likes':     self.likes,
            'created_at': self.created_at.isoformat(),
        }
