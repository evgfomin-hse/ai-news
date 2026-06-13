from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_health_service
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])

HEALTH_MEDIA_TYPE = "application/health+json"


@router.get("/live")
def liveness() -> JSONResponse:
    return JSONResponse(content={"status": "pass"}, media_type=HEALTH_MEDIA_TYPE)


@router.get("/ready")
def readiness(
    health: Annotated[HealthService, Depends(get_health_service)],
) -> JSONResponse:
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
