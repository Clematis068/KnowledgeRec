"""迁移脚本：新增通知表和私信表。"""
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
            CREATE TABLE IF NOT EXISTS notification (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                sender_id INT,
                type ENUM('system', 'follow', 'like', 'favorite', 'comment') NOT NULL,
                post_id INT,
                content TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_notification_user_id (user_id),
                INDEX idx_notification_is_read (is_read),
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (sender_id) REFERENCES user(id),
                FOREIGN KEY (post_id) REFERENCES post(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS message (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                content TEXT NOT NULL,
                msg_type ENUM('text', 'image', 'post_link') NOT NULL DEFAULT 'text',
                image_url TEXT,
                linked_post_id INT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_message_sender_id (sender_id),
                INDEX idx_message_receiver_id (receiver_id),
                FOREIGN KEY (sender_id) REFERENCES user(id),
                FOREIGN KEY (receiver_id) REFERENCES user(id),
                FOREIGN KEY (linked_post_id) REFERENCES post(id)
            )
            """,
        ]

        for stmt in statements:
            db.session.execute(text(stmt))

        db.session.commit()
        print("[OK] 已创建 notification 和 message 表")


if __name__ == '__main__':
    migrate()
