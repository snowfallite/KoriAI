"""Chart validators of tech.md §9.9."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.artifacts import ChartSpec


def chart(kind: str, points: list[dict[str, Any]], series: int = 1) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": "Цена",
        "x": {"type": "time"},
        "y": {"type": "value"},
        "series": [{"name": f"s{i}", "points": points} for i in range(series)],
    }


@pytest.mark.parametrize(
    ("kind", "point"),
    [
        ("line", {"x": "2026-01-05", "y": 1.5}),
        ("pie", {"x": "Акции", "y": 0.6}),
        ("candlestick", {"x": "2026-01-05", "o": 1, "h": 2, "l": 0.5, "c": 1.5}),
        ("heatmap", {"x": "SBER", "y_cat": "GAZP", "z": 0.4}),
    ],
)
def test_points_carry_the_fields_of_their_kind(kind: str, point: dict[str, Any]) -> None:
    assert ChartSpec.model_validate(chart(kind, [point])).kind == kind


@pytest.mark.parametrize(
    ("kind", "point"),
    [
        ("line", {"x": "2026-01-05"}),
        ("bar", {"x": "Q1", "z": 1}),
        ("candlestick", {"x": "2026-01-05", "o": 1, "h": 2, "l": 0.5}),
        ("candlestick", {"x": "2026-01-05", "y": 1}),
        ("heatmap", {"x": "SBER", "z": 0.4}),
        ("heatmap", {"x": "SBER", "y_cat": "GAZP"}),
    ],
)
def test_a_point_without_the_fields_of_its_kind_is_rejected(
    kind: str, point: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        ChartSpec.model_validate(chart(kind, [point]))


def test_a_pie_holds_at_most_12_slices() -> None:
    slices = [{"x": f"d{i}", "y": 1} for i in range(12)]
    ChartSpec.model_validate(chart("pie", slices))

    with pytest.raises(ValidationError):
        ChartSpec.model_validate(chart("pie", [*slices, {"x": "d12", "y": 1}]))


def test_a_chart_holds_1_to_12_series_and_at_most_5000_points() -> None:
    points = [{"x": i, "y": i} for i in range(500)]
    ChartSpec.model_validate(chart("line", points, series=10))

    for series in (11, 13, 0):
        bad = chart("line", points if series == 11 else [], series)
        with pytest.raises(ValidationError):
            ChartSpec.model_validate(bad)
