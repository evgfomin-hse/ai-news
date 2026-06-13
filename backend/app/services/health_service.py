from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.database_repository import DatabaseRepository

logger = logging.getLogger(__name__)

PASS = "pass"
FAIL = "fail"


@dataclass(frozen=True)
class ComponentCheck:
    component: str
    status: str
    observed_value_ms: float | None = None
    output: str | None = None


@dataclass(frozen=True)
class HealthReport:
    status: str
    checks: list[ComponentCheck] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.status == PASS


class HealthService:
    def __init__(self, session: Session) -> None:
        self._database = DatabaseRepository(session)

    def check_readiness(self) -> HealthReport:
        """Run every dependency check. The overall status fails if any component fails."""
        checks = [self._check_database()]
        status = PASS if all(c.status == PASS for c in checks) else FAIL
        return HealthReport(status=status, checks=checks)

    def _check_database(self) -> ComponentCheck:
        start = time.perf_counter()
        try:
            self._database.ping()
        except SQLAlchemyError as exc:
            root = getattr(exc, "orig", None) or exc
            msg = str(root).strip().splitlines()[0]
            logger.warning("Readiness database check failed: %s", msg)
            return ComponentCheck(component="database", status=FAIL, output=msg)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return ComponentCheck(component="database", status=PASS, observed_value_ms=elapsed_ms)
