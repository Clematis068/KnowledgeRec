from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler

from .config import Config

db = SQLAlchemy()
scheduler = APScheduler()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 跨域支持
    CORS(app)

    # 初始化数据库（启动时不强制连接，避免未装 MySQL 就报错）
    db.init_app(app)

    # 初始化定时任务调度器
    app.config['SCHEDULER_API_ENABLED'] = False
    scheduler.init_app(app)

    # 初始化 SocketIO
    from .socketio_instance import socketio
    socketio.init_app(app)

    # 注册 WebSocket 事件处理
    from . import events  # noqa: F401

    # 注册蓝图
    from .api.llm import llm_bp
    from .api.recommendation import rec_bp
    from .api.user import user_bp
    from .api.post import post_bp
    from .api.auth import auth_bp
    from .api.search import search_bp
    from .api.tag_taxonomy import tag_taxonomy_bp
    from .api.notification import notification_bp
    from .api.upload import upload_bp
    from .api.evaluation import evaluation_bp

    app.register_blueprint(llm_bp, url_prefix='/api/llm')
    app.register_blueprint(rec_bp, url_prefix='/api')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(post_bp, url_prefix='/api/post')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(tag_taxonomy_bp, url_prefix='/api')
    app.register_blueprint(notification_bp, url_prefix='/api/notification')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(evaluation_bp, url_prefix='/api/evaluation')

    # 注册预计算定时任务（每 6 小时执行一次）
    from .services.recommendation import recommendation_engine
    _register_precompute_job(app, recommendation_engine)

    return app


def _register_precompute_job(app, engine):
    """注册 CF/Swing 相似度矩阵预计算的定时任务。"""
    import logging
    logger = logging.getLogger('precompute')

    @scheduler.task('interval', id='precompute_similarity', hours=6, misfire_grace_time=3600)
    def precompute_similarity():
        with app.app_context():
            logger.info("定时预计算开始: CF + Swing 相似度矩阵")
            try:
                engine.precompute()
                logger.info("定时预计算完成")
            except Exception as e:
                logger.error("定时预计算失败: %s", e)

    scheduler.start()
