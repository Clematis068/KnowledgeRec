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
    app.register_blueprint(llm_bp, url_prefix='/api/llm')

    return app
