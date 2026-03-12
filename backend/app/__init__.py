from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from .config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 跨域支持
    CORS(app)

    # 初始化数据库（启动时不强制连接，避免未装 MySQL 就报错）
    db.init_app(app)

    # 注册蓝图
    from .api.llm import llm_bp
    from .api.recommendation import rec_bp
    from .api.user import user_bp
    from .api.post import post_bp
    from .api.auth import auth_bp
    from .api.search import search_bp
    from .api.tag_taxonomy import tag_taxonomy_bp

    app.register_blueprint(llm_bp, url_prefix='/api/llm')
    app.register_blueprint(rec_bp, url_prefix='/api')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(post_bp, url_prefix='/api/post')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(tag_taxonomy_bp, url_prefix='/api')

    return app
