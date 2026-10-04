"""Endpoints of the dev and ci environments only (tech.md §6.7)."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, Request

from app.contracts.api.health import DemoJobIn, DemoJobOut, EchoIn, EchoOut
from app.contracts.jobs import DemoEchoPayload
from app.contracts.stream import DevEchoEvent, RunFinishedEvent
from app.core.errors import AppError
from app.http.deps import CurrentUser
from app.http.errors import HTTP_ERRORS
from app.http.events import RunEventBus
from app.jobs.app import defer

ECHO_DELAY_S = 0.2


def dev_only(request: Request) -> None:
    if request.app.state.settings.APP_ENV not in {"dev", "ci"}:
        raise AppError(*HTTP_ERRORS[404])


router = APIRouter(prefix="/api/dev", tags=["dev"], dependencies=[Depends(dev_only)])


@router.post("/jobs/demo", status_code=202)
async def demo_job(body: DemoJobIn) -> DemoJobOut:
    return DemoJobOut(job_id=await defer(DemoEchoPayload(key=body.key, value=body.value)))


@router.post("/echo", status_code=202)
async def echo(body: EchoIn, user: CurrentUser, request: Request) -> EchoOut:
    """A stream of the user that sends dev.echo with the payload, then run.finished."""
    bus: RunEventBus = request.app.state.events
    stream_id = uuid.uuid4()
    bus.open(stream_id, user.user_id)

    def answer() -> None:
        bus.publish(stream_id, DevEchoEvent, payload=body.payload)
        bus.publish(stream_id, RunFinishedEvent, status="done", message_id=None, error=None)

    asyncio.get_running_loop().call_later(ECHO_DELAY_S, answer)
    return EchoOut(stream_id=stream_id)
