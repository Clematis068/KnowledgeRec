"""迁移脚本：为 user_behavior.behavior_type 增加 dislike 枚举值。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text

from app import create_app, db


def migrate():
    app = create_app()
    with app.app_context():
        result = db.session.execute(text("SHOW COLUMNS FROM user_behavior LIKE 'behavior_type'"))
        row = result.mappings().first()
        if not row:
            print("[WARN] 未找到 user_behavior.behavior_type")
            return

        column_type = row['Type']
        if 'dislike' in column_type:
            print("[SKIP] behavior_type 已包含 dislike")
            return

        db.session.execute(text(
            "ALTER TABLE user_behavior "
            "MODIFY COLUMN behavior_type "
            "ENUM('browse', 'like', 'favorite', 'comment', 'dislike') NOT NULL"
        ))
        db.session.commit()
        print("[OK] behavior_type 已新增 dislike")


if __name__ == '__main__':
    migrate()
