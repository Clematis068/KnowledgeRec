"""
迁移脚本：
1. tag.name 全局唯一 -> (domain_id, name) 联合唯一
2. 新增 tag_alias / pending_tag

用法:
  cd backend && uv run python -m scripts.migrate_tag_taxonomy
"""
import os
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models import *  # noqa: F401,F403


def ensure_tag_unique_constraint():
    inspector = inspect(db.engine)
    unique_constraints = inspector.get_unique_constraints("tag")

    single_name_constraint = next(
        (item["name"] for item in unique_constraints if item.get("column_names") == ["name"]),
        None,
    )
    composite_exists = any(
        item.get("column_names") == ["domain_id", "name"]
        for item in unique_constraints
    )

    if single_name_constraint:
        db.session.execute(text(f"ALTER TABLE tag DROP INDEX `{single_name_constraint}`"))
        print(f"[OK] 已删除旧唯一索引: {single_name_constraint}")

    if not composite_exists:
        db.session.execute(
            text("ALTER TABLE tag ADD CONSTRAINT uq_tag_domain_name UNIQUE (domain_id, name)")
        )
        print("[OK] 已新增联合唯一约束 uq_tag_domain_name")


def ensure_taxonomy_tables():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "tag_alias" not in tables:
        db.session.execute(text("""
            CREATE TABLE tag_alias (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                domain_id INT NOT NULL,
                canonical_tag_id INT NOT NULL,
                source VARCHAR(32) DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_tag_alias_domain_name UNIQUE (domain_id, name),
                FOREIGN KEY (domain_id) REFERENCES domain(id),
                FOREIGN KEY (canonical_tag_id) REFERENCES tag(id)
            )
        """))
        print("[OK] 已创建 tag_alias")

    if "pending_tag" not in tables:
        db.session.execute(text("""
            CREATE TABLE pending_tag (
                id INT AUTO_INCREMENT PRIMARY KEY,
                raw_name VARCHAR(128) NOT NULL,
                normalized_name VARCHAR(128),
                source_user_id INT NULL,
                source_post_id INT NULL,
                domain_id INT NULL,
                suggested_domain_id INT NULL,
                matched_tag_id INT NULL,
                confidence FLOAT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                llm_reason TEXT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (source_user_id) REFERENCES user(id),
                FOREIGN KEY (source_post_id) REFERENCES post(id),
                FOREIGN KEY (domain_id) REFERENCES domain(id),
                FOREIGN KEY (suggested_domain_id) REFERENCES domain(id),
                FOREIGN KEY (matched_tag_id) REFERENCES tag(id)
            )
        """))
        db.session.execute(text("CREATE INDEX idx_pending_tag_status ON pending_tag(status)"))
        print("[OK] 已创建 pending_tag")


def main():
    app = create_app()
    with app.app_context():
        ensure_tag_unique_constraint()
        ensure_taxonomy_tables()
        db.session.commit()
        print("[DONE] taxonomy 迁移完成")


if __name__ == "__main__":
    main()
