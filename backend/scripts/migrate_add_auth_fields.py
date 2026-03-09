"""
数据迁移脚本：为已有用户添加认证字段
- ALTER TABLE user ADD password_hash, gender
- CREATE TABLE user_tag
- 为已有用户设默认密码 123456、随机 gender、分配兴趣标签
- 模拟数据
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db
from app.models.user import User
from app.models.tag import Tag


def migrate():
    app = create_app()
    with app.app_context():
        # 1. 创建 user_tag 表（如果不存在）
        db.engine.execute("""
            CREATE TABLE IF NOT EXISTS user_tag (
                user_id INT NOT NULL,
                tag_id INT NOT NULL,
                PRIMARY KEY (user_id, tag_id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (tag_id) REFERENCES tag(id)
            )
        """)
        print("[OK] user_tag 表已创建")

        # 2. 添加 password_hash 和 gender 列（忽略已存在的错误）
        for stmt in [
            "ALTER TABLE user ADD COLUMN password_hash VARCHAR(256)",
            "ALTER TABLE user ADD COLUMN gender ENUM('male','female','other')",
        ]:
            try:
                db.engine.execute(stmt)
                print(f"[OK] {stmt}")
            except Exception as e:
                if 'Duplicate column' in str(e):
                    print(f"[SKIP] 列已存在: {stmt}")
                else:
                    print(f"[WARN] {e}")

        # 3. 为已有用户设默认密码和随机属性
        users = User.query.all()
        all_tags = Tag.query.all()

        for user in users:
            if not user.password_hash:
                user.set_password('123456')
            if not user.gender:
                user.gender = random.choice(['male', 'female', 'other'])
            if not user.interest_tags and all_tags:
                sample_size = min(random.randint(3, 8), len(all_tags))
                user.interest_tags = random.sample(all_tags, sample_size)

        db.session.commit()
        print(f"[OK] 已更新 {len(users)} 个用户的默认属性")


if __name__ == '__main__':
    migrate()
