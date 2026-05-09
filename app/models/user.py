from app import db
from datetime import datetime
import bcrypt
import json


class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name     = db.Column(db.String(100))
    avatar_url    = db.Column(db.String(500), default='/assets/images/default-avatar.png')
    bio           = db.Column(db.Text)
    role          = db.Column(db.Enum('user', 'admin'), default='user')
    is_verified   = db.Column(db.Boolean, default=False)
    verify_token  = db.Column(db.String(100))
    reset_token   = db.Column(db.String(100))
    reset_expires = db.Column(db.DateTime)
    oauth_provider = db.Column(db.String(20))
    oauth_id      = db.Column(db.String(100))
    preferences   = db.Column(db.JSON)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login    = db.Column(db.DateTime)

    # Relationships
    ratings         = db.relationship('Rating',                 backref='user', lazy='dynamic', cascade='all, delete-orphan')
    reviews         = db.relationship('Review',                 backref='user', lazy='dynamic', cascade='all, delete-orphan')
    watchlist       = db.relationship('Watchlist',              backref='user', lazy='dynamic', cascade='all, delete-orphan')
    rec_history     = db.relationship('RecommendationHistory',  backref='user', lazy='dynamic', cascade='all, delete-orphan')
    search_history  = db.relationship('SearchHistory',          backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def get_preferences(self) -> dict:
        if isinstance(self.preferences, dict):
            return self.preferences
        try:
            return json.loads(self.preferences) if self.preferences else {}
        except Exception:
            return {}

    def to_dict(self, include_private=False) -> dict:
        data = {
            'id':         self.id,
            'username':   self.username,
            'full_name':  self.full_name,
            'avatar_url': self.avatar_url,
            'bio':        self.bio,
            'role':       self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'preferences': self.get_preferences(),
        }
        if include_private:
            data['email']      = self.email
            data['is_verified'] = self.is_verified
            data['last_login'] = self.last_login.isoformat() if self.last_login else None
        return data

    def __repr__(self):
        return f'<User {self.username}>'
