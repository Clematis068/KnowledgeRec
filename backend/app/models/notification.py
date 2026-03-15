from app import db
from datetime import datetime


class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    type = db.Column(db.Enum('system', 'follow', 'like', 'favorite', 'comment', name='notification_type_enum'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    content = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    sender = db.relationship('User', foreign_keys=[sender_id], lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.username if self.sender else None,
            'sender_avatar': self.sender.avatar_url if self.sender else None,
            'type': self.type,
            'post_id': self.post_id,
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Message(db.Model):
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    msg_type = db.Column(db.Enum('text', 'image', 'post_link', name='msg_type_enum'), default='text', nullable=False)
    image_url = db.Column(db.Text, nullable=True)
    linked_post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    sender = db.relationship('User', foreign_keys=[sender_id], lazy='joined')
    receiver = db.relationship('User', foreign_keys=[receiver_id], lazy='joined')
    linked_post = db.relationship('Post', foreign_keys=[linked_post_id], lazy='joined')

    def to_dict(self):
        d = {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.username if self.sender else None,
            'sender_avatar': self.sender.avatar_url if self.sender else None,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.username if self.receiver else None,
            'content': self.content,
            'msg_type': self.msg_type or 'text',
            'image_url': self.image_url,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if self.linked_post:
            d['linked_post'] = {
                'id': self.linked_post.id,
                'title': self.linked_post.title,
                'summary': (self.linked_post.summary or '')[:120],
            }
        elif self.linked_post_id:
            d['linked_post'] = {'id': self.linked_post_id, 'title': '帖子已删除', 'summary': ''}
        else:
            d['linked_post'] = None
        return d


def create_notification(user_id, sender_id, notification_type, post_id=None, content=None):
    """创建通知的辅助函数。不给自己发通知。"""
    if user_id == sender_id:
        return None

    notification = Notification(
        user_id=user_id,
        sender_id=sender_id,
        type=notification_type,
        post_id=post_id,
        content=content,
    )
    db.session.add(notification)

    # 实时推送通知
    try:
        from app.events import emit_to_user
        db.session.flush()  # 让 ORM 加载 relationship
        emit_to_user(user_id, 'new_notification', notification.to_dict())
    except Exception:
        pass

    return notification
