"""
迁移脚本：新增半自动标签关系表 tag_relation

用法:
  cd backend && uv run python -m scripts.migrate_add_tag_relations
"""
import os
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models import *  # noqa: F401,F403


def ensure_tag_relation_table():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "tag_relation" in tables:
        print("[SKIP] tag_relation 已存在")
        return

    db.session.execute(text("""
        CREATE TABLE tag_relation (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_tag_id INT NOT NULL,
            target_tag_id INT NOT NULL,
            relation_type VARCHAR(24) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            source_method VARCHAR(32) NOT NULL DEFAULT 'semi-auto',
            llm_confidence FLOAT NOT NULL DEFAULT 0,
            sequence_support FLOAT NOT NULL DEFAULT 0,
            cooccurrence_score FLOAT NOT NULL DEFAULT 0,
            embedding_similarity FLOAT NOT NULL DEFAULT 0,
            final_score FLOAT NOT NULL DEFAULT 0,
            llm_reason TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT uq_tag_relation_pair UNIQUE (source_tag_id, target_tag_id, relation_type),
            FOREIGN KEY (source_tag_id) REFERENCES tag(id),
            FOREIGN KEY (target_tag_id) REFERENCES tag(id)
        )
    """))
    db.session.execute(text("CREATE INDEX idx_tag_relation_status ON tag_relation(status)"))
    db.session.execute(text("CREATE INDEX idx_tag_relation_type ON tag_relation(relation_type)"))
    db.session.execute(text("CREATE INDEX idx_tag_relation_score ON tag_relation(final_score)"))
    print("[OK] 已创建 tag_relation")


def main():
    app = create_app()
    with app.app_context():
        ensure_tag_relation_table()
        db.session.commit()
        print("[DONE] tag_relation 迁移完成")


if __name__ == "__main__":
    main()
