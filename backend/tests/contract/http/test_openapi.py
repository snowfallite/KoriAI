"""The OpenAPI the SPA types come from (S1-04 AC 2, tech.md §6.1, §7, §12.1)."""

from typing import Any

from app.config import Settings
from app.main import create_app

EVENT_TYPES = {
    "run.queued",
    "run.started",
    "run.routed",
    "step.started",
    "tool.started",
    "tool.finished",
    "artifact.created",
    "source.added",
    "text.delta",
    "text.reset",
    "run.warning",
    "run.finished",
    "dev.echo",
}


def openapi() -> dict[str, Any]:
    return create_app(Settings(_env_file=None)).openapi()


def test_schemas_carry_the_stream_and_artifact_models() -> None:
    schemas = openapi()["components"]["schemas"]

    assert {"StreamEvent", "ChartSpec", "TableSpec", "ImageSpec", "SourceRef"} <= schemas.keys()


def test_schemas_carry_the_prop_models_of_the_ui_kit() -> None:
    # The §13.2 props need them before any route sends them.
    schemas = openapi()["components"]["schemas"]

    assert {"Money", "UserOut", "BrokerAccountOut", "PeriodCode"} <= schemas.keys()


def test_stream_event_is_a_union_tagged_by_type() -> None:
    stream_event = openapi()["components"]["schemas"]["StreamEvent"]

    assert stream_event["discriminator"]["propertyName"] == "type"
    assert set(stream_event["discriminator"]["mapping"]) == EVENT_TYPES
    assert len(stream_event["oneOf"]) == len(EVENT_TYPES)


def test_every_operation_answers_errors_with_error_out() -> None:
    schema = openapi()
    error_out = {"$ref": "#/components/schemas/ErrorOut"}

    for path in schema["paths"].values():
        for operation in path.values():
            responses = operation["responses"]
            for status in ("4XX", "5XX"):
                assert responses[status]["content"]["application/json"]["schema"] == error_out
            assert "422" not in responses
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_responses_list_every_field_as_required() -> None:
    # The backend always sends every field, so the SPA types need no optional marks.
    error_out = openapi()["components"]["schemas"]["ErrorOut"]

    assert set(error_out["required"]) == set(error_out["properties"])
