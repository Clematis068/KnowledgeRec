from app import db
from datetime import datetime


class Domain(db.Model):
    __tablename__ = 'domain'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text)

    tags = db.relationship('Tag', backref='domain', lazy='dynamic')
    posts = db.relationship('Post', backref='domain', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
        }
