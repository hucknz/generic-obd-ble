"""Binary sensor platform for Generic OBD BLE."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import STATE_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_VEHICLE_PROFILE_ID, DATA_SENSOR_META, DOMAIN, NAME
from .entity import GenericObdBleEntity
from .profiles import get_profile_by_id

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "mil_on": BinarySensorEntityDescription(
        key="mil_on",
        icon="mdi:engine",
        name="Malfunction indicator lamp",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    keys = set(coordinator.data.keys())
    profile = get_profile_by_id(entry.data.get(CONF_VEHICLE_PROFILE_ID))
    profile_meta: dict[str, dict[str, Any]] = coordinator.data.get(DATA_SENSOR_META, {})

    entities = [
        GenericObdBleBinarySensor(
            coordinator,
            entry,
            sensor_key=sensor_desc,
            description=BINARY_SENSOR_TYPES[sensor_desc],
        )
        for sensor_desc in BINARY_SENSOR_TYPES
        if sensor_desc in keys
    ]

    if profile:
        for key, meta in profile_meta.items():
            if key not in keys:
                continue
            if meta.get("entity_platform") != "binary_sensor":
                continue
            entities.append(
                GenericObdBleBinarySensor(
                    coordinator,
                    entry,
                    sensor_key=key,
                    description=BinarySensorEntityDescription(
                        key=key,
                        name=meta.get("name") or key.replace("_", " ").title(),
                        icon=meta.get("icon", "mdi:toggle-switch"),
                    ),
                )
            )

    async_add_devices(entities)


class GenericObdBleBinarySensor(
    GenericObdBleEntity,
    BinarySensorEntity,
    RestoreEntity,
):
    """generic_obd_ble binary_sensor class."""

    def __init__(
        self,
        coordinator,
        config_entry,
        sensor_key: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry)
        self._sensor = sensor_key
        self._description = description
        self._restored_is_on: bool | None = None
        self._attr_name = f"{NAME} {description.name}"
        self._attr_device_class = description.device_class

    async def async_added_to_hass(self) -> None:
        """Restore last known state on startup until fresh data arrives."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state:
            return
        self._restored_is_on = last_state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if the binary_sensor is on."""
        live_value = self.coordinator.data.get(self._sensor)
        if live_value is not None:
            return bool(live_value)
        return self._restored_is_on

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._description.icon
