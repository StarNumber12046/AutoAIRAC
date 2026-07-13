"""Tests for AIRAC cycle utilities."""

from datetime import date, timedelta
from pathlib import Path

from autoairac.airac.cycle import (
    airac_cycle_dates,
    current_airac_cycle,
    cycle_from_date,
    is_cycle_expired,
    parse_cycle_from_navdata_header,
)


def test_cycle_from_reference_date() -> None:
    assert cycle_from_date(date(2024, 1, 25)) == 2401


def test_cycle_year_rollover() -> None:
    # 13th cycle of 2024 rolls into 2501, not 2414.
    assert cycle_from_date(date(2025, 1, 22)) == 2413
    assert cycle_from_date(date(2025, 1, 23)) == 2501


def test_current_cycle_july_2026() -> None:
    assert cycle_from_date(date(2026, 7, 13)) == 2607


def test_parse_navdata_header() -> None:
    header = "I\n1100 Version - data cycle 2607, build 20260701, ..."
    assert parse_cycle_from_navdata_header(header) == 2607


def test_parse_xplane_navdata_second_line() -> None:
    from autoairac.config import PathsConfig
    from autoairac.simulators.xplane12 import XPlane12Adapter

    sample = "I\n1200 Version - data cycle 2607, build 20260701, metadata FixXP1200.\n"
    path = Path("earth_fix_sample.dat")
    path.write_text(sample, encoding="utf-8")
    try:
        assert XPlane12Adapter._cycle_from_file(path) == 2607
    finally:
        path.unlink()


def test_expired_cycle() -> None:
    effective, expiry = airac_cycle_dates(2401)
    assert effective == date(2024, 1, 25)
    assert is_cycle_expired(2401, today=expiry) is False
    assert is_cycle_expired(2401, today=expiry + timedelta(days=1)) is True


def test_current_cycle_is_int() -> None:
    cycle = current_airac_cycle()
    assert 2000 < cycle < 9999