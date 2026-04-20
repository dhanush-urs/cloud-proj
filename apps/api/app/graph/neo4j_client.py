from app.core.config import get_settings


class Neo4jClient:
    def __init__(self):
        try:
            from neo4j import GraphDatabase  # lazy — optional dependency
        except ImportError as exc:
            raise RuntimeError(
                "The 'neo4j' Python package is not installed. "
                "Graph features are unavailable in this environment. "
                "Install it with: pip install neo4j"
            ) from exc

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
