"""Lock for Kia Connect EU integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from ._vendor.hyundai_kia_connect_api import Vehicle

from .const import DOMAIN
from .coordinator import KiaConnectEuDataUpdateCoordinator
from .entity import KiaConnectEuEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for vehicle_id in coordinator.vehicle_manager.vehicles:
        vehicle: Vehicle = coordinator.vehicle_manager.vehicles[vehicle_id]
        entities.append(KiaConnectEuLock(coordinator, vehicle))

    async_add_entities(entities)


PARALLEL_UPDATES = 1


class KiaConnectEuLock(LockEntity, KiaConnectEuEntity):
    def __init__(
        self,
        coordinator: KiaConnectEuDataUpdateCoordinator,
        vehicle: Vehicle,
    ) -> None:
        KiaConnectEuEntity.__init__(self, coordinator, vehicle)
        self._attr_unique_id = f"{DOMAIN}_{vehicle.id}_door_lock"
        self._attr_translation_key = "door_lock"

    @property
    def icon(self) -> str | None:
        return "mdi:lock" if self.is_locked else "mdi:lock-open-variant"

    @property
    def is_locked(self) -> bool | None:
        return cast(bool | None, self.vehicle.is_locked)

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.async_lock_vehicle(self.vehicle.id)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.async_unlock_vehicle(self.vehicle.id)
