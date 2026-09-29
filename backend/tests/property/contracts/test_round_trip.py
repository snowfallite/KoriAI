"""Every contract survives a JSON round trip and rejects unknown fields (S1-04 AC 3).

Data comes from the JSON schema of each contract, the same schema the SPA types come from:
a value the schema allows must validate, so the TS types never promise what the API refuses.
"""

import importlib
import pkgutil
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel, TypeAdapter, ValidationError

import app.contracts
from app.contracts.agent import ToolSpec
from app.contracts.api.chat import MessageBlock, ThreadOut
from app.contracts.artifacts import MAX_PIE_SLICES, POINT_FIELDS
from app.contracts.common import Page
from app.contracts.stream import StreamEvent


def contract_models() -> list[type[BaseModel]]:
    modules = [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(app.contracts.__path__, "app.contracts.")
    ]
    found = {
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == module.__name__
    }
    return sorted(found, key=lambda model: (model.__module__, model.__qualname__))


# ToolSpec holds a class, not JSON; a generic Page takes an item type.
TARGETS: list[Any] = [
    *(m for m in contract_models() if m not in {ToolSpec, Page} and not m.__name__.startswith("_")),
    Page[ThreadOut],
    StreamEvent,
    MessageBlock,
]


def _fill_chart(spec: dict[str, Any]) -> dict[str, Any]:
    # The schema cannot say which point fields a chart kind needs (§9.9 validators).
    needed = POINT_FIELDS.get(spec["kind"], ("y",))
    blank = {name: "row" if name == "y_cat" else 0.0 for name in needed}
    series = [
        {
            **s,
            "points": [
                {**p, **{k: v for k, v in blank.items() if p.get(k) is None}}
                for p in s["points"][:MAX_PIE_SLICES]
            ],
        }
        for s in spec["series"]
    ]
    return {**spec, "series": series}


FIXES: dict[str, Callable[[Any], Any]] = {"ChartSpec": _fill_chart}
TIMEZONES = [UTC, timezone(timedelta(hours=3)), timezone(-timedelta(hours=5, minutes=30))]
URL = r"https?://[a-z]{1,12}\.[a-z]{2,6}(/[a-z0-9]{1,8}){0,2}"


def json_values() -> st.SearchStrategy[Any]:
    scalars = (
        st.none()
        | st.booleans()
        | st.integers()
        | st.floats(allow_nan=False, allow_infinity=False)
        | st.text()
    )
    return st.recursive(
        scalars,
        lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(), inner, max_size=3),
        max_leaves=8,
    )


def strings(schema: dict[str, Any]) -> st.SearchStrategy[str]:
    if "pattern" in schema:
        # JSON Schema regexes follow ECMA-262, where \d means [0-9].
        return st.from_regex(re.compile(schema["pattern"], re.ASCII), fullmatch=True)
    match schema.get("format"):
        case "date-time":
            # Hypothesis takes naive bounds and attaches the zones itself.
            low, high = datetime(1900, 1, 1), datetime(2200, 1, 1)  # noqa: DTZ001
            moments = st.datetimes(low, high, timezones=st.sampled_from(TIMEZONES))
            return moments.map(datetime.isoformat)
        case "date":
            return st.dates(date(1900, 1, 1), date(2200, 1, 1)).map(date.isoformat)
        case "uuid":
            return st.uuids().map(str)
        case "uri":
            return st.from_regex(URL, fullmatch=True)
    return st.text(min_size=schema.get("minLength", 0), max_size=schema.get("maxLength"))


def with_tag(name: str, tag: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda raw: {**raw, name: tag}


def from_schema(schema: dict[str, Any], defs: dict[str, Any]) -> st.SearchStrategy[Any]:
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/$defs/")
        fix = FIXES.get(name, lambda value: value)
        return st.deferred(lambda: from_schema(defs[name], defs)).map(fix)
    if "const" in schema:
        return st.just(schema["const"])
    if "enum" in schema:
        return st.sampled_from(schema["enum"])
    if tagged := schema.get("discriminator"):
        # OpenAPI requires the tag even when a variant gives it a default.
        return st.one_of(
            [
                from_schema({"$ref": ref}, defs).map(with_tag(tagged["propertyName"], tag))
                for tag, ref in tagged["mapping"].items()
            ]
        )
    if variants := schema.get("anyOf", schema.get("oneOf")):
        return st.one_of([from_schema(variant, defs) for variant in variants])
    match schema.get("type"):
        case None:
            return json_values()
        case "null":
            return st.none()
        case "boolean":
            return st.booleans()
        case "integer":
            return st.integers(schema.get("minimum"), schema.get("maximum"))
        case "number":
            return st.floats(
                schema.get("minimum"), schema.get("maximum"), allow_nan=False, allow_infinity=False
            )
        case "string":
            return strings(schema)
        case "array":
            low = schema.get("minItems", 0)
            high = max(low, min(schema.get("maxItems", 2), 2))
            return st.lists(from_schema(schema["items"], defs), min_size=low, max_size=high)
        case "object" if "properties" in schema:
            required = set(schema.get("required", []))
            fields = {name: from_schema(s, defs) for name, s in schema["properties"].items()}
            return st.fixed_dictionaries(
                {name: s for name, s in fields.items() if name in required},
                optional={name: s for name, s in fields.items() if name not in required},
            )
        case "object":
            keys = from_schema(schema.get("propertyNames", {"type": "string"}), defs)
            values = from_schema(schema.get("additionalProperties", {}), defs)
            return st.dictionaries(keys, values, max_size=2)
    raise NotImplementedError(schema)


@cache
def adapter_of(target: Any) -> TypeAdapter[Any]:
    return TypeAdapter(target)


@cache
def values_of(target: Any) -> st.SearchStrategy[Any]:
    schema = adapter_of(target).json_schema(mode="validation")
    fix = FIXES.get(getattr(target, "__name__", ""), lambda value: value)
    return from_schema(schema, schema.get("$defs", {})).map(fix)


def name_of(target: Any) -> str:
    return str(getattr(target, "__qualname__", target))


# 145 types: a fixed budget per type keeps the test near 30 s in both profiles.
@pytest.mark.parametrize("target", TARGETS, ids=name_of)
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(data=st.data())
def test_json_round_trip_and_no_unknown_fields(target: Any, data: st.DataObject) -> None:
    adapter = adapter_of(target)
    raw = data.draw(values_of(target))
    value = adapter.validate_python(raw)

    assert adapter.validate_python(adapter.dump_python(value, mode="json")) == value
    with pytest.raises(ValidationError) as caught:
        adapter.validate_python({**raw, "unknown_field": 1})
    assert [error["type"] for error in caught.value.errors()] == ["extra_forbidden"]


def test_class_names_are_unique() -> None:
    # The OpenAPI names schemas by class (app/http/openapi.py).
    names = [model.__name__ for model in contract_models()]

    assert len(names) == len(set(names))


def test_every_contract_is_closed_and_frozen() -> None:
    open_models = [
        model.__qualname__
        for model in contract_models()
        if model.model_config.get("extra") != "forbid" or not model.model_config.get("frozen")
    ]

    assert open_models == []
