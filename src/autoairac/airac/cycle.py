"""AIRAC cycle calculation and navdata header parsing."""

from __future__ import annotations

import re
from datetime import date, timedelta

# Reference: AIRAC 2401 effective 25 Jan 2024 (ICAO 28-day cycle).
_REFERENCE_CYCLE = 2401
_REFERENCE_EFFECTIVE = date(2024, 1, 25)
_CYCLE_LENGTH_DAYS = 28
_CYCLES_PER_YEAR = 13

_CYCLE_HEADER_RE = re.compile(
    r"(?:data\s+cycle|AIRAC|cycle)\s*[:\s]*(\d{4})",
    re.IGNORECASE,
)


def prev_airac_cycle(cycle: int) -> int:
    """Return the AIRAC cycle immediately before *cycle*."""
    year = cycle // 100
    seq = cycle % 100
    if seq <= 1:
        return (year - 1) * 100 + _CYCLES_PER_YEAR
    return year * 100 + (seq - 1)


def next_airac_cycle(cycle: int | None = None) -> int:
    """Cycle that follows *cycle* (or the one after the current cycle)."""
    cycle = cycle if cycle is not None else current_airac_cycle()
    year = cycle // 100
    seq = cycle % 100
    if seq >= _CYCLES_PER_YEAR:
        return (year + 1) * 100 + 1
    return year * 100 + (seq + 1)


def airac_cycle_dates(cycle: int) -> tuple[date, date]:
    """Return (effective_date, expiry_date) for an AIRAC cycle.

    *expiry_date* is the last day the cycle is valid (inclusive).
    """
    year = cycle // 100
    seq = cycle % 100
    ref_year = _REFERENCE_CYCLE // 100
    ref_seq = _REFERENCE_CYCLE % 100
    offset_cycles = (year - ref_year) * _CYCLES_PER_YEAR + (seq - ref_seq)
    effective = _REFERENCE_EFFECTIVE + timedelta(days=offset_cycles * _CYCLE_LENGTH_DAYS)
    expiry = effective + timedelta(days=_CYCLE_LENGTH_DAYS - 1)
    return effective, expiry


def cycle_from_date(when: date | None = None) -> int:
    """Return the AIRAC cycle effective on *when* (defaults to today)."""
    when = when or date.today()
    cycle = _REFERENCE_CYCLE
    effective, expiry = airac_cycle_dates(cycle)

    while when < effective:
        cycle = prev_airac_cycle(cycle)
        effective, expiry = airac_cycle_dates(cycle)

    while when > expiry:
        cycle = next_airac_cycle(cycle)
        effective, expiry = airac_cycle_dates(cycle)

    return cycle


def current_airac_cycle() -> int:
    """AIRAC cycle currently in effect."""
    return cycle_from_date(date.today())


def is_cycle_expired(installed_cycle: int, *, today: date | None = None) -> bool:
    """True when *installed_cycle* is older than the cycle in effect today."""
    today = today or date.today()
    _, expiry = airac_cycle_dates(installed_cycle)
    return today > expiry


def parse_cycle_from_navdata_header(text: str) -> int | None:
    """Extract a 4-digit AIRAC cycle from a navdata file header line."""
    match = _CYCLE_HEADER_RE.search(text)
    if not match:
        return None
    return int(match.group(1))