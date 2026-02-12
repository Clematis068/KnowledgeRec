import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # MySQL
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'MYSQL_URI',
        'mysql+pymysql://root:password@localhost:3306/knowledge_community'
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
    QWEN_MODEL = os.getenv('QWEN_MODEL', 'qwen-plus')