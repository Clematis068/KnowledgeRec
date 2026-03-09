from app import db
from datetime import datetime

# 帖子-标签关联表
post_tag = db.Table(
    'post_tag',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True),
)


class Post(db.Model):
    __tablename__ = 'post'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(512))          # LLM读取生成summ，改成结构化的prompt
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    content_embedding = db.Column(db.JSON)       # 1024d
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    tags = db.relationship('Tag', secondary=post_tag, backref=db.backref('posts', lazy='dynamic'))
    behaviors = db.relationship('UserBehavior', backref='post', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'author_id': self.author_id,
            'author_name': self.author.username if self.author else None,
            'domain_id': self.domain_id,
            'domain_name': self.domain.name if self.domain else None,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'tags': [t.name for t in self.tags],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
