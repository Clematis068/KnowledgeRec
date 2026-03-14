from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# 用户-兴趣标签关联表
user_tag = db.Table(
    'user_tag',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    email = db.Column(db.String(128), unique=True)
    gender = db.Column(db.Enum('male', 'female', 'other', name='gender_enum'))
    avatar_url = db.Column(db.String(256))
    bio = db.Column(db.Text)
    interest_embedding = db.Column(db.JSON)    # 1024-dim weighted avg of interacted posts
    interest_profile = db.Column(db.Text)       # LLM generated interest description
    last_login_region = db.Column(db.String(32))
    last_login_timezone = db.Column(db.String(64))
    last_login_time_slot = db.Column(db.String(16))
    last_active_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    posts = db.relationship('Post', backref='author', lazy='dynamic')
    behaviors = db.relationship('UserBehavior', backref='user', lazy='dynamic')
    interest_tags = db.relationship('Tag', secondary=user_tag, backref=db.backref('interested_users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'gender': self.gender,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'interest_profile': self.interest_profile,
            'interest_tags': [t.to_dict() for t in self.interest_tags],
            'last_login_region': self.last_login_region,
            'last_login_timezone': self.last_login_timezone,
            'last_login_time_slot': self.last_login_time_slot,
            'last_active_at': self.last_active_at.isoformat() if self.last_active_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
