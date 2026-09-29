"""OpenAPI of the app plus the models that no route body carries (tech.md §12.1)."""

from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.models import OpenAPI
from fastapi.openapi.utils import get_openapi
from pydantic import TypeAdapter
from pydantic.json_schema import GenerateJsonSchema

from app.contracts.artifacts import ChartSpec, ImageSpec, SourceRef, TableSpec
from app.contracts.common import ErrorOut
from app.contracts.stream import StreamEvent

# Every error leaves the API as ErrorOut (§6.1); FastAPI then skips its own 422 schema.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "4XX": {"model": ErrorOut},
    "5XX": {"model": ErrorOut},
}

# The SPA gets these from the SSE stream and inside artifacts, never as a route body.
EXTRA_TYPES: tuple[Any, ...] = (StreamEvent, ChartSpec, TableSpec, ImageSpec, SourceRef)


def install(app: FastAPI) -> None:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            generator = GenerateJsonSchema(ref_template="#/components/schemas/{model}")
            _, extra = generator.generate_definitions(
                [(t, "serialization", TypeAdapter(t).core_schema) for t in EXTRA_TYPES]
            )
            components = schema.setdefault("components", {})
            # Class names are unique across app.contracts (tests/property/contracts), so a
            # shared name means the same model.
            components["schemas"] = dict(sorted({**extra, **components.get("schemas", {})}.items()))
            # get_openapi drops nulls this way; the extra models go through the same pass.
            app.openapi_schema = jsonable_encoder(
                OpenAPI(**schema), by_alias=True, exclude_none=True
            )
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
