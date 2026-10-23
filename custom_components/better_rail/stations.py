"""Station list shared with the Better Rail server (Israel Railways station IDs)."""

from functools import cache
import json
from pathlib import Path
from typing import TypedDict


class Station(TypedDict):
    """A rail station."""

    id: str
    he: str
    en: str


@cache
def get_stations() -> dict[str, Station]:
    """Return all stations keyed by ID."""
    path = Path(__file__).parent / "stations.json"
    return {s["id"]: s for s in json.loads(path.read_text(encoding="utf-8"))}


def station_name(station_id: str) -> str:
    """Return a display name for a station ID."""
    station = get_stations().get(station_id)
    return station["en"] if station else station_id
