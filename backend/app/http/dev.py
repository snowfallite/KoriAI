"""Endpoints of the dev and ci environments only (tech.md §6.7)."""

from fastapi import APIRouter, Depends, Request

from app.contracts.api.health import DemoJobIn, DemoJobOut
from app.contracts.jobs import DemoEchoPayload
from app.core.errors import AppError
from app.http.errors import HTTP_ERRORS
from app.jobs.app import defer


def dev_only(request: Request) -> None:
    if request.app.state.settings.APP_ENV not in {"dev", "ci"}:
        raise AppError(*HTTP_ERRORS[404])


router = APIRouter(prefix="/api/dev", tags=["dev"], dependencies=[Depends(dev_only)])


@router.post("/jobs/demo", status_code=202)
async def demo_job(body: DemoJobIn) -> DemoJobOut:
    return DemoJobOut(job_id=await defer(DemoEchoPayload(key=body.key, value=body.value)))
