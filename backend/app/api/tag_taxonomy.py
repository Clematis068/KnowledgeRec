from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app import db
from app.models.tag import Tag
from app.models.tag_taxonomy import TagRelation
from app.utils.auth import login_required

tag_taxonomy_bp = Blueprint("tag_taxonomy", __name__)

REVIEWABLE_STATUSES = {"pending", "approved", "rejected", "auto_approved"}
MUTABLE_STATUSES = {"pending", "approved", "rejected"}


def _serialize_relation(relation):
    source_tag = relation.source_tag
    target_tag = relation.target_tag
    domain = source_tag.domain if source_tag else None
    return {
        "id": relation.id,
        "relation_type": relation.relation_type,
        "status": relation.status,
        "source_method": relation.source_method,
        "final_score": relation.final_score,
        "llm_confidence": relation.llm_confidence,
        "sequence_support": relation.sequence_support,
        "cooccurrence_score": relation.cooccurrence_score,
        "embedding_similarity": relation.embedding_similarity,
        "llm_reason": relation.llm_reason,
        "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
        "created_at": relation.created_at.isoformat() if relation.created_at else None,
        "source_tag": {
            "id": source_tag.id,
            "name": source_tag.name,
            "domain_id": source_tag.domain_id,
        } if source_tag else None,
        "target_tag": {
            "id": target_tag.id,
            "name": target_tag.name,
            "domain_id": target_tag.domain_id,
        } if target_tag else None,
        "domain": {
            "id": domain.id,
            "name": domain.name,
        } if domain else None,
    }


def _parse_statuses(raw_statuses):
    if not raw_statuses:
        return ["pending"]
    statuses = [item.strip() for item in raw_statuses.split(",") if item.strip()]
    return [item for item in statuses if item in REVIEWABLE_STATUSES] or ["pending"]


@tag_taxonomy_bp.route("/tag-relations/review", methods=["GET"])
@login_required
def list_tag_relations():
    statuses = _parse_statuses(request.args.get("statuses"))
    relation_type = (request.args.get("relation_type") or "").strip().upper()
    domain_id = request.args.get("domain_id", type=int)
    keyword = (request.args.get("keyword") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    stmt = (
        db.select(TagRelation)
        .join(Tag, Tag.id == TagRelation.source_tag_id)
        .filter(TagRelation.status.in_(statuses))
        .order_by(TagRelation.final_score.desc(), TagRelation.id.asc())
    )
    if relation_type:
        stmt = stmt.filter(TagRelation.relation_type == relation_type)
    if domain_id:
        stmt = stmt.filter(Tag.domain_id == domain_id)
    if keyword:
        stmt = stmt.filter(
            or_(
                Tag.name.ilike(f"%{keyword}%"),
                TagRelation.target_tag.has(Tag.name.ilike(f"%{keyword}%")),
            )
        )

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_relation(item) for item in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "statuses": statuses,
        }
    )


@tag_taxonomy_bp.route("/tag-relations/review/summary", methods=["GET"])
@login_required
def tag_relation_review_summary():
    rows = (
        db.session.query(TagRelation.status, db.func.count(TagRelation.id))
        .group_by(TagRelation.status)
        .all()
    )
    return jsonify({"status_counts": {status: count for status, count in rows}})


@tag_taxonomy_bp.route("/tag-relations/review/<int:relation_id>", methods=["POST"])
@login_required
def review_tag_relation(relation_id):
    relation = db.session.get(TagRelation, relation_id)
    if not relation:
        return jsonify({"error": "关系不存在"}), 404

    data = request.get_json() or {}
    status = (data.get("status") or "").strip().lower()
    if status not in MUTABLE_STATUSES:
        return jsonify({"error": "status 只支持 pending / approved / rejected"}), 400

    relation.status = status
    db.session.commit()
    return jsonify({"message": "审核状态已更新", "item": _serialize_relation(relation)})


@tag_taxonomy_bp.route("/tag-relations/review/batch", methods=["POST"])
@login_required
def batch_review_tag_relations():
    data = request.get_json() or {}
    relation_ids = data.get("relation_ids") or []
    status = (data.get("status") or "").strip().lower()
    if status not in MUTABLE_STATUSES:
        return jsonify({"error": "status 只支持 pending / approved / rejected"}), 400
    if not relation_ids or not all(isinstance(item, int) for item in relation_ids):
        return jsonify({"error": "relation_ids 必须是非空整数列表"}), 400

    relations = db.session.scalars(
        db.select(TagRelation).filter(TagRelation.id.in_(relation_ids))
    ).all()
    if not relations:
        return jsonify({"error": "未找到可更新的关系"}), 404

    for relation in relations:
        relation.status = status
    db.session.commit()
    return jsonify(
        {
            "message": "批量审核完成",
            "updated_count": len(relations),
            "status": status,
        }
    )
