from sqlalchemy.orm import Session

from app.repositories.database_repository import DatabaseRepository


class HealthService:
    def __init__(self, session: Session) -> None:
        self._database = DatabaseRepository(session)

    def check_database_connection(self) -> None:
        self._database.ping()
