import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # MySQL
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'MYSQL_URI',
        'mysql+pymysql://root:password@localhost:3306/knowledge_community_old'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Neo4j
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

    # 通义千问 (DashScope)
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    DASHSCOPE_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    QWEN_MODEL = os.getenv('QWEN_MODEL', 'qwen-max')

    # 邮件验证码（未配置 SMTP 时自动降级为开发模式）
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'true').lower() == 'true'
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'false').lower() == 'true'

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))

    # 阿里云内容审核（全民一淘 LightApp）
    ALIYUN_ACCESS_KEY_ID = os.getenv('ALIYUN_ACCESS_KEY_ID', '')
    ALIYUN_ACCESS_KEY_SECRET = os.getenv('ALIYUN_ACCESS_KEY_SECRET', '')
    ALIYUN_AUDIT_WORKSPACE_ID = os.getenv('ALIYUN_AUDIT_WORKSPACE_ID', 'ws-yxjd1v75e5qlded8')
    ALIYUN_AUDIT_API_KEY = os.getenv('ALIYUN_AUDIT_API_KEY', '')
    ALIYUN_AUDIT_ENDPOINT = os.getenv(
        'ALIYUN_AUDIT_ENDPOINT', 'quanmiaolightapp.cn-beijing.aliyuncs.com'
    )
