from datetime import datetime

from app import db


class TagAlias(db.Model):
    __tablename__ = "tag_alias"
    __table_args__ = (
        db.UniqueConstraint("domain_id", "name", name="uq_tag_alias_domain_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False, index=True)
    canonical_tag_id = db.Column(db.Integer, db.ForeignKey("tag.id"), nullable=False, index=True)
    source = db.Column(db.String(32), default="user")
    created_at = db.Column(db.DateTime, default=datetime.now)

    canonical_tag = db.relationship("Tag", backref=db.backref("aliases", lazy="dynamic"))
    domain = db.relationship("Domain")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "domain_id": self.domain_id,
            "canonical_tag_id": self.canonical_tag_id,
            "source": self.source,
        }


class PendingTag(db.Model):
    __tablename__ = "pending_tag"

    id = db.Column(db.Integer, primary_key=True)
    raw_name = db.Column(db.String(128), nullable=False)
    normalized_name = db.Column(db.String(128))
    source_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    source_post_id = db.Column(db.Integer, db.ForeignKey("post.id"), index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), index=True)
    suggested_domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), index=True)
    matched_tag_id = db.Column(db.Integer, db.ForeignKey("tag.id"), index=True)
    confidence = db.Column(db.Float)
    status = db.Column(db.String(16), default="pending", nullable=False, index=True)
    llm_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    source_user = db.relationship("User", foreign_keys=[source_user_id])
    source_post = db.relationship("Post", foreign_keys=[source_post_id])
    domain = db.relationship("Domain", foreign_keys=[domain_id])
    suggested_domain = db.relationship("Domain", foreign_keys=[suggested_domain_id])
    matched_tag = db.relationship("Tag", foreign_keys=[matched_tag_id])

    def to_dict(self):
        return {
            "id": self.id,
            "raw_name": self.raw_name,
            "normalized_name": self.normalized_name,
            "source_user_id": self.source_user_id,
            "source_post_id": self.source_post_id,
            "domain_id": self.domain_id,
            "suggested_domain_id": self.suggested_domain_id,
            "matched_tag_id": self.matched_tag_id,
            "confidence": self.confidence,
            "status": self.status,
            "llm_reason": self.llm_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
