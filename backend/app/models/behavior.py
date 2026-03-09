from app import db
from datetime import datetime


class UserBehavior(db.Model):
    __tablename__ = 'user_behavior'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    behavior_type = db.Column(db.Enum('browse', 'like', 'favorite', 'comment', 'dislike', name='behavior_enum'), nullable=False)
    comment_text = db.Column(db.Text)       # only for comment type
    parent_id = db.Column(db.Integer, db.ForeignKey('user_behavior.id'), nullable=True)  # 回复的父评论ID
    duration = db.Column(db.Integer)         # browse duration in seconds
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)

    parent = db.relationship('UserBehavior', remote_side=[id], backref='replies')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'post_id': self.post_id,
            'behavior_type': self.behavior_type,
            'comment_text': self.comment_text,
            'parent_id': self.parent_id,
            'duration': self.duration,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def to_comment_dict(self):
        reply_to = None
        if self.parent_id and self.parent:
            reply_to = self.parent.user.username if self.parent.user else None
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'post_id': self.post_id,
            'comment_text': self.comment_text,
            'parent_id': self.parent_id,
            'reply_to_username': reply_to,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserFollow(db.Model):
    __tablename__ = 'user_follow'

    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class UserBlockedAuthor(db.Model):
    __tablename__ = 'user_blocked_author'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)


class UserBlockedDomain(db.Model):
    __tablename__ = 'user_blocked_domain'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
