from neo4j import GraphDatabase
from ..config import Config


class Neo4jService:
    """Neo4j 图数据库驱动封装"""

    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
                connection_timeout=3,
                max_connection_lifetime=60,
            )
        return self._driver

    def run_query(self, cypher, parameters=None):
        """执行只读查询，返回 list[dict]"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            print(f"[Neo4j] 查询失败: {e}")
            return []

    def run_write(self, cypher, parameters=None):
        """执行写入操作"""
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, parameters or {}))

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


neo4j_service = Neo4jService()
