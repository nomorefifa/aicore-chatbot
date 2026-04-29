import os
from neo4j import GraphDatabase


class GraphStore:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def run(self, query: str, **params) -> list:
        with self._driver.session() as session:
            return list(session.run(query, **params))

    def verify(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
