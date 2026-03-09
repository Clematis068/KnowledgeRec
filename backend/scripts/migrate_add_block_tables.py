"""迁移脚本：新增作者/领域屏蔽表。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text

from app import create_app, db


def migrate():
    app = create_app()
    with app.app_context():
        statements = [
            """
            CREATE TABLE IF NOT EXISTS user_blocked_author (
                user_id INT NOT NULL,
                author_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, author_id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (author_id) REFERENCES user(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_blocked_domain (
                user_id INT NOT NULL,
                domain_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, domain_id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (domain_id) REFERENCES domain(id)
            )
            """,
        ]

        for stmt in statements:
            db.session.execute(text(stmt))

        db.session.commit()
        print("[OK] 已创建屏蔽作者/领域表")


if __name__ == '__main__':
    migrate()
