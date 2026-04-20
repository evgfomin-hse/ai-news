from sqlalchemy import text
from sqlalchemy.orm import Session


class DatabaseRepository:
    """Low-level connectivity checks (no domain models)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> None:
        """Raises SQLAlchemyError if the database is not reachable."""
        self._session.execute(text("SELECT 1"))
