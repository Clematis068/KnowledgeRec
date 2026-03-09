"""迁移脚本：user_behavior 表新增 parent_id 字段（支持嵌套评论）"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db

app = create_app()

with app.app_context():
    db.session.execute(db.text(
        "ALTER TABLE user_behavior ADD COLUMN parent_id INT NULL"
    ))
    db.session.execute(db.text(
        "ALTER TABLE user_behavior ADD CONSTRAINT fk_parent_comment "
        "FOREIGN KEY (parent_id) REFERENCES user_behavior(id)"
    ))
    db.session.commit()
    print("Done: user_behavior.parent_id 字段已添加")
