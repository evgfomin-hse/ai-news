from sqlalchemy import text
from sqlalchemy.orm import Session


class DatabaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> None:
        self._session.execute(text("SELECT 1"))
