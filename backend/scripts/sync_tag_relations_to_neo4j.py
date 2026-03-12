"""
将审核通过的标签关系同步到 Neo4j。

用法:
  cd backend && uv run python -m scripts.sync_tag_relations_to_neo4j
  cd backend && uv run python -m scripts.sync_tag_relations_to_neo4j --statuses auto_approved approved --clear-existing
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.models.tag_taxonomy import TagRelation
from app.services.neo4j_service import neo4j_service
from app.services.tag_taxonomy_service import tag_taxonomy_service

SUPPORTED_RELATIONS = {"PREREQUISITE", "PARENT_OF", "RELATED_TO"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--statuses",
        nargs="+",
        default=["auto_approved", "approved"],
        help="同步哪些状态的关系",
    )
    parser.add_argument("--clear-existing", action="store_true", help="先删除同类型旧边再重建")
    return parser.parse_args()


def clear_existing_edges():
    for relation_type in SUPPORTED_RELATIONS:
        neo4j_service.run_write(f"MATCH ()-[r:{relation_type}]->() DELETE r")
        print(f"[CLEAN] 已清空 {relation_type} 边")


def sync_relation(relation):
    if relation.relation_type not in SUPPORTED_RELATIONS:
        return

    source_tag = relation.source_tag
    target_tag = relation.target_tag
    if not source_tag or not target_tag:
        return

    tag_taxonomy_service.sync_tag_to_neo4j(source_tag)
    tag_taxonomy_service.sync_tag_to_neo4j(target_tag)

    cypher = (
        f"MATCH (a:Tag {{id: $source_tag_id}}), (b:Tag {{id: $target_tag_id}}) "
        f"MERGE (a)-[r:{relation.relation_type}]->(b) "
        "SET r.score = $score, "
        "    r.status = $status, "
        "    r.source_method = $source_method, "
        "    r.updated_at = datetime($updated_at)"
    )
    neo4j_service.run_write(
        cypher,
        {
            "source_tag_id": relation.source_tag_id,
            "target_tag_id": relation.target_tag_id,
            "score": relation.final_score or 0.0,
            "status": relation.status,
            "source_method": relation.source_method,
            "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
        },
    )


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        if args.clear_existing:
            clear_existing_edges()

        relations = (
            TagRelation.query
            .filter(TagRelation.status.in_(args.statuses))
            .order_by(TagRelation.final_score.desc(), TagRelation.id.asc())
            .all()
        )
        if not relations:
            print("[SKIP] 没有需要同步的 tag relation")
            return

        synced = 0
        for relation in relations:
            try:
                sync_relation(relation)
                synced += 1
            except Exception as exc:
                print(f"[WARN] 同步失败 relation_id={relation.id}: {exc}")

        print(f"[DONE] 已同步 {synced} 条标签关系到 Neo4j")


if __name__ == "__main__":
    main()
