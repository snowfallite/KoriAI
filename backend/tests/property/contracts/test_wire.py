"""Wire forms of decimals and time hold for every value (tech.md §6.1)."""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter

from app.contracts.common import DECIMAL_PATTERN, DecimalStr, UtcDatetime

decimal_str: TypeAdapter[Decimal] = TypeAdapter(DecimalStr)
utc_datetime: TypeAdapter[datetime] = TypeAdapter(UtcDatetime)

day = timedelta(hours=23, minutes=59)
offsets = st.timedeltas(min_value=-day, max_value=day).map(timezone)
# Stored times fall far inside this range; year 1 with a positive offset has no UTC form.
low, high = datetime(1900, 1, 1), datetime(2200, 1, 1)  # noqa: DTZ001 - Hypothesis bounds


@given(st.decimals(allow_nan=False, allow_infinity=False))
def test_decimal_str_always_writes_the_pattern(value: Decimal) -> None:
    wire = decimal_str.dump_python(value, mode="json")

    assert re.fullmatch(DECIMAL_PATTERN, wire, re.ASCII)
    assert decimal_str.validate_python(wire) == value


@given(st.datetimes(low, high, timezones=offsets))
def test_time_always_goes_out_in_utc_with_z(moment: datetime) -> None:
    wire = utc_datetime.dump_python(utc_datetime.validate_python(moment), mode="json")

    assert wire.endswith("Z")
    assert utc_datetime.validate_python(wire) == moment
