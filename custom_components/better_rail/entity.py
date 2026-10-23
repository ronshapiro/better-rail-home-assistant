"""Base entity for Better Rail."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Journey
from .const import ATTRIBUTION, DOMAIN
from .coordinator import BetterRailCoordinator


class BetterRailEntity(CoordinatorEntity[BetterRailCoordinator]):
    """An entity describing one of the next departures."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BetterRailCoordinator,
        key: str,
        index: int,
        unique_id: str,
        title: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"suffix": f" +{index}" if index else ""}
        self._attr_unique_id = f"{unique_id}_{key}{index or ''}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=title,
        )

    @property
    def journey(self) -> Journey | None:
        """Return the journey this entity describes, if any."""
        data = self.coordinator.data
        return data[self._index] if self._index < len(data) else None
