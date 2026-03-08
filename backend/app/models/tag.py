from app import db


class Tag(db.Model):
    __tablename__ = 'tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    embedding = db.Column(db.JSON)  # 1024-dim vector

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'domain_id': self.domain_id,
        }
