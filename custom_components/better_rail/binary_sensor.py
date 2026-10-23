"""Binary sensors for Better Rail."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEPARTURES_COUNT
from .coordinator import BetterRailConfigEntry
from .entity import BetterRailEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BetterRailConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors from a config entry."""
    async_add_entities(
        BetterRailCancelledSensor(
            entry.runtime_data, "cancelled", i, entry.unique_id or entry.entry_id, entry.title
        )
        for i in range(DEPARTURES_COUNT)
    )


class BetterRailCancelledSensor(BetterRailEntity, BinarySensorEntity):
    """Whether a departure has been cancelled."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the train is cancelled."""
        journey = self.journey
        return journey.cancelled if journey else None
