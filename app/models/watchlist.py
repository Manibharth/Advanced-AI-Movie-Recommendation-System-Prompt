from app import db
from datetime import datetime


class Watchlist(db.Model):
    __tablename__ = 'watchlist'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id',  ondelete='CASCADE'), nullable=False)
    movie_id   = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False)
    status     = db.Column(db.Enum('want_to_watch', 'watching', 'watched'), default='want_to_watch')
    added_at   = db.Column(db.DateTime, default=datetime.utcnow)
    watched_at = db.Column(db.DateTime)

    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id', name='uq_watchlist'),)

    movie = db.relationship('Movie', backref=db.backref('watchlisted_by', lazy='dynamic'))

    def to_dict(self):
        return {
            'id':         self.id,
            'user_id':    self.user_id,
            'movie_id':   self.movie_id,
            'status':     self.status,
            'added_at':   self.added_at.isoformat(),
            'watched_at': self.watched_at.isoformat() if self.watched_at else None,
            'movie':      self.movie.to_dict() if self.movie else None,
        }
