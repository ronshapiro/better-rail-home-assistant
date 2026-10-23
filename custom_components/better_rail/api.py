"""Client for the Better Rail timetable API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import API_TIMEOUT, API_URL

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class BetterRailError(Exception):
    """Raised when the Better Rail API cannot be queried."""


@dataclass
class Journey:
    """One itinerary between the configured stations."""

    departure: datetime
    arrival: datetime | None
    delay: int
    platform: str | None
    train_number: str
    trains: int
    cancelled: bool

    @property
    def expected_departure(self) -> datetime:
        """Scheduled departure shifted by the live delay."""
        return self.departure + timedelta(minutes=self.delay)


def _parse_time(value: str | None) -> datetime | None:
    """Parse the API's naive Israel wall-clock timestamps."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=ISRAEL_TZ)
    except ValueError:
        return None


def parse_journeys(payload: dict[str, Any]) -> list[Journey]:
    """Convert a searchTrainLuzForDateTime response into journeys."""
    journeys: list[Journey] = []
    for travel in (payload.get("result") or {}).get("travels") or []:
        trains = travel.get("trains") or []
        if not trains:
            continue
        first = trains[0]
        departure = _parse_time(first.get("departureTime") or travel.get("departureTime"))
        if departure is None:
            continue
        position = first.get("trainPosition") or {}
        platform = first.get("originPlatform")
        journeys.append(
            Journey(
                departure=departure,
                arrival=_parse_time(trains[-1].get("arrivalTime") or travel.get("arrivalTime")),
                delay=int(position.get("calcDiffMinutes") or 0),
                platform=str(platform) if platform else None,
                train_number=str(first.get("trainNumber")),
                trains=len(trains),
                cancelled=bool(first.get("isCancelled")),
            )
        )
    return journeys


class BetterRailApi:
    """Thin async client for the Better Rail API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def async_get_journeys(
        self, start: str, destination: str, when: datetime
    ) -> list[Journey]:
        """Return the day's journeys for the date of `when` (naive Israel time)."""
        params = {
            "fromStation": start,
            "toStation": destination,
            "date": when.strftime("%Y-%m-%d"),
            "hour": when.strftime("%H:%M"),
            "scheduleType": "1",
            "systemType": "1",
            "languageId": "English",
        }
        try:
            async with self._session.get(
                API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise BetterRailError(str(err)) from err
        if not isinstance(payload, dict):
            raise BetterRailError("Unexpected response from Better Rail API")
        return parse_journeys(payload)
