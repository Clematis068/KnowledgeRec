from app import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True)
    avatar_url = db.Column(db.String(256))
    bio = db.Column(db.Text)
    interest_embedding = db.Column(db.JSON)    # 1024-dim weighted avg of interacted posts
    interest_profile = db.Column(db.Text)       # LLM generated interest description
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    posts = db.relationship('Post', backref='author', lazy='dynamic')
    behaviors = db.relationship('UserBehavior', backref='user', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'bio': self.bio,
            'interest_profile': self.interest_profile,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
