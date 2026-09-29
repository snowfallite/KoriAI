"""Artifacts and sources of an answer (tech.md §9.9)."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.common import Contract, UtcDatetime

type ChartKind = Literal[
    "line", "area", "bar", "stacked_bar", "pie", "candlestick", "scatter", "heatmap", "waterfall"
]


class AxisSpec(Contract):
    type: Literal["time", "category", "value", "log"]
    label: str | None = None
    format: (
        Literal["date", "month", "quarter", "year", "money", "percent", "number", "compact"] | None
    ) = None
    unit: str | None = None  # 'RUB', 'USD', '%', 'x'


class ChartPoint(Contract):
    x: str | float  # ISO date, category or number
    y: float | None = None  # line, area, bar, pie, scatter, waterfall
    o: float | None = None  # candlestick
    h: float | None = None
    l: float | None = None  # noqa: E741 - the contract name of the low price
    c: float | None = None
    y_cat: str | None = None  # heatmap row
    z: float | None = None  # heatmap value


class SeriesSpec(Contract):
    name: str
    points: list[ChartPoint]
    axis: Literal["y", "y2"] = "y"
    role: Literal["primary", "positive", "negative", "neutral", "benchmark"] | None = None


# Every other kind needs y.
POINT_FIELDS: dict[ChartKind, tuple[str, ...]] = {
    "candlestick": ("o", "h", "l", "c"),
    "heatmap": ("y_cat", "z"),
}
MAX_POINTS = 5000
MAX_PIE_SLICES = 12


class ChartSpec(Contract):
    """Floats serve display only; exact values live in a TableSpec as DecimalStr."""

    kind: ChartKind
    title: str
    subtitle: str | None = None
    x: AxisSpec
    y: AxisSpec
    y2: AxisSpec | None = None
    series: list[SeriesSpec] = Field(min_length=1, max_length=12)
    source_ids: list[str] = []

    @model_validator(mode="after")
    def _check_points(self) -> Self:
        points = [point for series in self.series for point in series.points]
        if len(points) > MAX_POINTS:
            raise ValueError(f"a chart holds at most {MAX_POINTS} points")
        fields = POINT_FIELDS.get(self.kind, ("y",))
        if any(getattr(point, name) is None for point in points for name in fields):
            raise ValueError(f"{self.kind} points need {', '.join(fields)}")
        # The builder folds the tail into «Прочее».
        if self.kind == "pie" and any(len(s.points) > MAX_PIE_SLICES for s in self.series):
            raise ValueError(f"a pie holds at most {MAX_PIE_SLICES} slices")
        return self


class ColumnSpec(Contract):
    key: str
    label: str
    type: Literal["text", "number", "money", "percent", "date", "instrument"]
    currency: str | None = None  # for money
    digits: int | None = None


class TableSpec(Contract):
    title: str
    columns: list[ColumnSpec] = Field(min_length=1, max_length=12)
    # Text, DecimalStr, ISO date or instrument uid.
    rows: list[dict[str, str | None]] = Field(max_length=200)
    total: dict[str, str | None] | None = None
    note: str | None = None
    instruments: dict[str, InstrumentBrief] = {}  # for columns of type 'instrument'
    source_ids: list[str] = []


class ImageSpec(Contract):
    source: Literal["logo", "web", "document_page"]
    logo_base: str | None = None
    url: str | None = None
    document_id: UUID | None = None
    page: int | None = None
    alt: str
    caption: str | None = None
    size: Literal["sm", "md", "lg"] = "md"
    source_ids: list[str] = []


class ArtifactOut(Contract):
    id: UUID
    local_id: Annotated[str, StringConstraints(pattern=r"^[cti][0-9]+$")]
    kind: Literal["chart", "table", "image"]
    spec: ChartSpec | TableSpec | ImageSpec
    image_url: str | None  # for image: the media proxy path (§6.4)
    created_at: UtcDatetime


class SourceRef(Contract):
    local_id: Annotated[str, StringConstraints(pattern=r"^s[0-9]+$")]
    kind: Literal["web", "document", "tinvest", "edisclosure"]
    title: str
    url: str | None
    publisher: str | None
    published_at: date | None
    document_id: UUID | None
    page: int | None
    snippet: str | None
