from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_health_service
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])

# Per the IETF health-check draft, health responses use this media type so
# intermediaries don't treat them as ordinary application/json.
HEALTH_MEDIA_TYPE = "application/health+json"


@router.get("/live")
def liveness() -> JSONResponse:
    """Liveness probe: the process is up and serving requests.

    Touches no external dependencies on purpose — a database outage must not make
    an orchestrator kill and restart an otherwise-healthy instance. Always 200.
    """
    return JSONResponse(content={"status": "pass"}, media_type=HEALTH_MEDIA_TYPE)


@router.get("/ready")
def readiness(
    health: Annotated[HealthService, Depends(get_health_service)],
) -> JSONResponse:
    """Readiness probe: the instance can serve traffic (dependencies reachable).

    Returns 200 when every dependency check passes and 503 otherwise, so a load
    balancer stops routing to an instance that can't reach the database.
    """
    report = health.check_readiness()
    checks = {
        c.component: {
            key: value
            for key, value in (
                ("status", c.status),
                ("observedValue", c.observed_value_ms),
                ("observedUnit", "ms" if c.observed_value_ms is not None else None),
                ("output", c.output),
            )
            if value is not None
        }
        for c in report.checks
    }
    return JSONResponse(
        content={"status": report.status, "checks": checks},
        status_code=200 if report.is_healthy else 503,
        media_type=HEALTH_MEDIA_TYPE,
    )
