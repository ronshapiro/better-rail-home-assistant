"""DataUpdateCoordinator for the Better Rail integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ISRAEL_TZ, BetterRailApi, BetterRailError, Journey
from .const import DEFAULT_SCAN_INTERVAL, DEPARTURES_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)

type BetterRailConfigEntry = ConfigEntry[BetterRailCoordinator]


def is_upcoming(journey: Journey, now) -> bool:
    """Return whether the train has not left its origin yet.

    A reported delay pushes back the moment the train actually leaves, so the
    journey stays upcoming until its scheduled departure plus that delay. A
    negative delay is ignored so an early running train does not disappear
    before its scheduled time.
    """
    return journey.departure + timedelta(minutes=max(journey.delay, 0)) >= now


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
            update_interval=DEFAULT_SCAN_INTERVAL,
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
        return result[:DEPARTURES_COUNT]
