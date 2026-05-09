from app import db
from datetime import datetime


class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    search_query = db.Column('query', db.String(255), nullable=False)
    results    = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'query':      self.search_query,
            'results':    self.results,
            'created_at': self.created_at.isoformat(),
        }
