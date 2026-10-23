"""Sensors for Better Rail."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import Journey
from .const import DEPARTURES_COUNT
from .coordinator import BetterRailConfigEntry
from .entity import BetterRailEntity


@dataclass(kw_only=True, frozen=True)
class BetterRailSensorEntityDescription(SensorEntityDescription):
    """Describes a Better Rail sensor."""

    value_fn: Callable[[Journey], StateType | datetime]


SENSORS: tuple[BetterRailSensorEntityDescription, ...] = (
    BetterRailSensorEntityDescription(
        key="departure",
        translation_key="departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda j: j.departure,
    ),
    BetterRailSensorEntityDescription(
        key="expected_departure",
        translation_key="expected_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda j: j.expected_departure,
    ),
    BetterRailSensorEntityDescription(
        key="arrival",
        translation_key="arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda j: j.arrival,
    ),
    BetterRailSensorEntityDescription(
        key="departure_delay",
        translation_key="departure_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda j: j.delay,
    ),
    BetterRailSensorEntityDescription(
        key="platform",
        translation_key="platform",
        value_fn=lambda j: j.platform,
    ),
    BetterRailSensorEntityDescription(
        key="trains",
        translation_key="trains",
        value_fn=lambda j: j.trains,
    ),
    BetterRailSensorEntityDescription(
        key="train_number",
        translation_key="train_number",
        value_fn=lambda j: j.train_number,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BetterRailConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors from a config entry."""
    async_add_entities(
        BetterRailSensor(
            entry.runtime_data, description, i, entry.unique_id or entry.entry_id, entry.title
        )
        for description in SENSORS
        for i in range(DEPARTURES_COUNT)
    )


class BetterRailSensor(BetterRailEntity, SensorEntity):
    """A Better Rail sensor."""

    entity_description: BetterRailSensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: BetterRailSensorEntityDescription,
        index: int,
        unique_id: str,
        title: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key, index, unique_id, title)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        journey = self.journey
        return self.entity_description.value_fn(journey) if journey else None
