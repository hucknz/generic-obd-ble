"""Binary sensor platform for Generic OBD BLE."""

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME
from .entity import GenericObdBleEntity

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
    entities = [
        GenericObdBleBinarySensor(coordinator, entry, sensor_desc)
        for sensor_desc in BINARY_SENSOR_TYPES
        if sensor_desc in keys
    ]
    async_add_devices(entities)


class GenericObdBleBinarySensor(GenericObdBleEntity, BinarySensorEntity):
    """generic_obd_ble binary_sensor class."""

    def __init__(
        self,
        coordinator,
        config_entry,
        sensor: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry)
        self._sensor = sensor
        self._attr_name = f"{NAME} {BINARY_SENSOR_TYPES[sensor].name}"
        # self.entity_description = BINARY_SENSOR_TYPES[sensor]
        self._attr_device_class = BINARY_SENSOR_TYPES[sensor].device_class

    @property
    def is_on(self):
        """Return true if the binary_sensor is on."""
        return self.coordinator.data.get(self._sensor)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return BINARY_SENSOR_TYPES[self._sensor].icon
