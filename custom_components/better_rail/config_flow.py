"""Config flow for Better Rail."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .api import ISRAEL_TZ, BetterRailApi, BetterRailError
from .const import CONF_DESTINATION, CONF_START, DOMAIN
from .stations import get_stations, station_name

_LOGGER = logging.getLogger(__name__)


def _station_selector() -> SelectSelector:
    options = [
        SelectOptionDict(value=s["id"], label=f"{s['en']} / {s['he']}")
        for s in sorted(get_stations().values(), key=lambda s: s["en"])
    ]
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


class BetterRailConfigFlow(ConfigFlow, domain=DOMAIN):
    """Better Rail config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the start and end stations."""
        errors: dict[str, str] = {}
        if user_input:
            start, destination = user_input[CONF_START], user_input[CONF_DESTINATION]
            if start == destination:
                errors["base"] = "same_station"
            else:
                api = BetterRailApi(async_get_clientsession(self.hass))
                try:
                    await api.async_get_journeys(
                        start, destination, dt_util.now().astimezone(ISRAEL_TZ)
                    )
                except BetterRailError:
                    _LOGGER.exception("Unable to reach the Better Rail API")
                    errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(f"{start} {destination}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{station_name(start)} → {station_name(destination)}",
                    data=user_input,
                )

        selector = _station_selector()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_START): selector,
                    vol.Required(CONF_DESTINATION): selector,
                }
            ),
            errors=errors,
        )
