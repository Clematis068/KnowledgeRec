from app import db


class Tag(db.Model):
    __tablename__ = 'tag'
    __table_args__ = (
        db.UniqueConstraint('domain_id', 'name', name='uq_tag_domain_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    embedding = db.Column(db.JSON)  # 1024-dim vector

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'domain_id': self.domain_id,
        }
