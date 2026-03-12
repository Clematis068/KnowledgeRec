"""
数据迁移脚本：为登录上下文推荐补充 user / post 字段。
- user: last_login_region, last_login_timezone, last_login_time_slot, last_active_at
- post: target_regions, target_time_slots

用法:
  cd backend && uv run python -m scripts.migrate_add_context_fields
"""
import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db


ALTER_STATEMENTS = [
    "ALTER TABLE user ADD COLUMN last_login_region VARCHAR(32)",
    "ALTER TABLE user ADD COLUMN last_login_timezone VARCHAR(64)",
    "ALTER TABLE user ADD COLUMN last_login_time_slot VARCHAR(16)",
    "ALTER TABLE user ADD COLUMN last_active_at DATETIME",
    "ALTER TABLE post ADD COLUMN target_regions JSON",
    "ALTER TABLE post ADD COLUMN target_time_slots JSON",
]


def migrate():
    app = create_app()
    with app.app_context():
        for stmt in ALTER_STATEMENTS:
            try:
                db.session.execute(text(stmt))
                db.session.commit()
                print(f"[OK] {stmt}")
            except Exception as exc:
                db.session.rollback()
                if 'Duplicate column' in str(exc):
                    print(f"[SKIP] 列已存在: {stmt}")
                else:
                    print(f"[WARN] {stmt} -> {exc}")


if __name__ == '__main__':
    migrate()
