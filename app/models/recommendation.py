from app import db
from datetime import datetime


class RecommendationHistory(db.Model):
    __tablename__ = 'recommendation_history'

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id',  ondelete='CASCADE'), nullable=False)
    movie_id        = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False)
    rec_type        = db.Column(db.String(50))
    confidence      = db.Column(db.Float, default=0)
    reason          = db.Column(db.String(255))
    clicked         = db.Column(db.Boolean, default=False)
    added_watchlist = db.Column(db.Boolean, default=False)
    rated           = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    movie = db.relationship('Movie', backref=db.backref('recommended_history', lazy='dynamic'))

    def to_dict(self):
        return {
            'id':         self.id,
            'user_id':    self.user_id,
            'movie_id':   self.movie_id,
            'rec_type':   self.rec_type,
            'confidence': self.confidence,
            'reason':     self.reason,
            'clicked':    self.clicked,
            'created_at': self.created_at.isoformat(),
            'movie':      self.movie.to_dict() if self.movie else None,
        }


class AIFeedback(db.Model):
    __tablename__ = 'ai_feedback'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.String(100))
    message    = db.Column(db.Text, nullable=False)
    response   = db.Column(db.Text)
    helpful    = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'session_id': self.session_id,
            'message':    self.message,
            'response':   self.response,
            'helpful':    self.helpful,
            'created_at': self.created_at.isoformat(),
        }
