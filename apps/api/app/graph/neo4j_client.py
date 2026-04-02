from neo4j import GraphDatabase

from app.core.config import get_settings


class Neo4jClient:
    def __init__(self):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

    def close(self):
        self.driver.close()

    def execute_write(self, query: str, parameters: dict | None = None):
        with self.driver.session() as session:
            return session.execute_write(
                lambda tx: tx.run(query, parameters or {}).consume()
            )

    def execute_read(self, query: str, parameters: dict | None = None):
        with self.driver.session() as session:
            result = session.execute_read(
                lambda tx: list(tx.run(query, parameters or {}))
            )
            return result
