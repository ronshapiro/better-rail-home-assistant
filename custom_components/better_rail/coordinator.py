"""DataUpdateCoordinator for the Better Rail integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ISRAEL_TZ, BetterRailApi, BetterRailError, Journey
from .const import (
    DELAY_WATCH_WINDOW,
    DEPARTURES_COUNT,
    DOMAIN,
    SCAN_INTERVAL_FAR,
    SCAN_INTERVAL_IDLE,
    SCAN_INTERVAL_IMMINENT,
    SCAN_INTERVAL_SOON,
)

_LOGGER = logging.getLogger(__name__)

type BetterRailConfigEntry = ConfigEntry[BetterRailCoordinator]


def is_upcoming(journey: Journey, now: datetime) -> bool:
    """Return whether the train has not left its origin yet.

    A reported delay pushes back the moment the train actually leaves, so the
    journey stays upcoming until its scheduled departure plus that delay. A
    negative delay is ignored so an early running train does not disappear
    before its scheduled time.
    """
    return journey.departure + timedelta(minutes=max(journey.delay, 0)) >= now


# (time before the scheduled departure, polling interval from then on)
_TIERS = (
    (timedelta(hours=3), SCAN_INTERVAL_FAR),
    (timedelta(hours=1), SCAN_INTERVAL_SOON),
    (timedelta(minutes=15), SCAN_INTERVAL_IMMINENT),
)
_MIN_INTERVAL = timedelta(seconds=15)


def next_update_interval(journeys: list[Journey], now: datetime) -> timedelta:
    """Choose how long to wait before the next poll.

    Polling speeds up as the next scheduled departure approaches, and stays
    fast while that train (or any other within the next hour) is delayed or is
    still waiting past its scheduled time, so delay changes are picked up
    promptly. The wait never overshoots the moment the next tier begins.
    """
    if not journeys:
        return SCAN_INTERVAL_IDLE

    for journey in journeys:
        until = journey.departure - now
        if (journey.delay or until <= timedelta(0)) and until <= DELAY_WATCH_WINDOW:
            return SCAN_INTERVAL_IMMINENT

    until_next = journeys[0].departure - now
    interval = SCAN_INTERVAL_IDLE
    for threshold, tier_interval in _TIERS:
        if until_next <= threshold:
            interval = tier_interval
    for threshold, _ in _TIERS:
        if until_next > threshold:
            interval = min(interval, until_next - threshold)
    return max(interval, _MIN_INTERVAL)


class BetterRailCoordinator(DataUpdateCoordinator[list[Journey]]):
    """Fetch the next departures between two stations."""

    config_entry: BetterRailConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BetterRailConfigEntry,
        start: str,
        destination: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_IMMINENT,
        )
        self._api = BetterRailApi(async_get_clientsession(hass))
        self._start = start
        self._destination = destination

    async def _async_update_data(self) -> list[Journey]:
        now = dt_util.now().astimezone(ISRAEL_TZ)
        try:
            journeys = await self._api.async_get_journeys(
                self._start, self._destination, now
            )
        except BetterRailError as err:
            raise UpdateFailed(
                f"Unable to retrieve data from the Better Rail API: {err}"
            ) from err

        upcoming = [j for j in journeys if is_upcoming(j, now)]

        # The API returns one service day at a time; near the end of the day
        # continue with the first trains of tomorrow.
        if len(upcoming) < DEPARTURES_COUNT:
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0)
            try:
                upcoming += [
                    j
                    for j in await self._api.async_get_journeys(
                        self._start, self._destination, tomorrow
                    )
                    if is_upcoming(j, now)
                ]
            except BetterRailError as err:
                _LOGGER.debug("Could not fetch tomorrow's departures: %s", err)

        seen: set[tuple[str, object]] = set()
        result: list[Journey] = []
        for journey in sorted(upcoming, key=lambda j: j.departure):
            key = (journey.train_number, journey.departure)
            if key not in seen:
                seen.add(key)
                result.append(journey)
        result = result[:DEPARTURES_COUNT]
        self.update_interval = next_update_interval(result, now)
        return result
