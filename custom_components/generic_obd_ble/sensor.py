"""Sensor platform for Generic OBD BLE."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_VEHICLE_PROFILE_ID,
    DATA_SENSOR_META,
    DOMAIN,
    NAME,
)
from .entity import GenericObdBleEntity
from .profiles import get_profile_by_id

RESERVED_DATA_KEYS = {
    "adapter_name",
    "adapter_address",
    "supported_pids",
    "mil_on",
    "vehicle_profile",
    DATA_SENSOR_META,
}

PROFILE_DIAGNOSTIC_KEYS = {
    "profile_probe_status",
    "profile_probe_supported_count",
    "profile_probe_supported_entities",
    "profile_probe_unsupported_entities",
}

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "engine_coolant_temp": SensorEntityDescription(
        key="engine_coolant_temp",
        name="Engine coolant temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "engine_rpm": SensorEntityDescription(
        key="engine_rpm",
        name="Engine RPM",
        icon="mdi:gauge",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "vehicle_speed": SensorEntityDescription(
        key="vehicle_speed",
        name="Vehicle speed",
        icon="mdi:speedometer",
        native_unit_of_measurement="km/h",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "intake_air_temp": SensorEntityDescription(
        key="intake_air_temp",
        name="Intake air temperature",
        icon="mdi:thermometer-lines",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "maf": SensorEntityDescription(
        key="maf",
        name="Mass air flow",
        icon="mdi:air-filter",
        native_unit_of_measurement="g/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "throttle_position": SensorEntityDescription(
        key="throttle_position",
        name="Throttle position",
        icon="mdi:car-cruise-control",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "engine_runtime": SensorEntityDescription(
        key="engine_runtime",
        name="Engine runtime",
        icon="mdi:timer-outline",
        native_unit_of_measurement="s",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "fuel_level": SensorEntityDescription(
        key="fuel_level",
        name="Fuel level",
        icon="mdi:gas-station",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ambient_air_temp": SensorEntityDescription(
        key="ambient_air_temp",
        name="Ambient air temperature",
        icon="mdi:home-thermometer-outline",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "control_module_voltage": SensorEntityDescription(
        key="control_module_voltage",
        name="Control module voltage",
        icon="mdi:car-battery",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "confirmed_dtc_count": SensorEntityDescription(
        key="confirmed_dtc_count",
        name="Confirmed DTC count",
        icon="mdi:engine-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "active_dtcs": SensorEntityDescription(
        key="active_dtcs",
        name="Active DTCs",
        icon="mdi:alert-circle-outline",
    ),
    "profile_probe_status": SensorEntityDescription(
        key="profile_probe_status",
        name="Profile probe status",
        icon="mdi:check-network-outline",
    ),
    "profile_probe_supported_count": SensorEntityDescription(
        key="profile_probe_supported_count",
        name="Profile supported entity count",
        icon="mdi:counter",
    ),
    "profile_probe_supported_entities": SensorEntityDescription(
        key="profile_probe_supported_entities",
        name="Profile supported entities",
        icon="mdi:playlist-check",
    ),
    "profile_probe_unsupported_entities": SensorEntityDescription(
        key="profile_probe_unsupported_entities",
        name="Profile unsupported entities",
        icon="mdi:playlist-remove",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    keys = set(coordinator.data.keys())
    profile_meta: dict[str, dict[str, Any]] = coordinator.data.get(DATA_SENSOR_META, {})
    profile = get_profile_by_id(entry.data.get(CONF_VEHICLE_PROFILE_ID))

    entities: list[GenericObdBleSensor] = []

    for sensor_key, descriptor in SENSOR_TYPES.items():
        if sensor_key in keys:
            entities.append(
                GenericObdBleSensor(
                    coordinator,
                    entry,
                    sensor_key=sensor_key,
                    description=descriptor,
                )
            )

    for key in keys:
        if key in SENSOR_TYPES or key in RESERVED_DATA_KEYS:
            continue

        key_meta = profile_meta.get(key)
        if key_meta and key_meta.get("entity_platform") == "binary_sensor":
            continue

        descriptor = _description_from_meta(key, key_meta)
        entities.append(
            GenericObdBleSensor(
                coordinator,
                entry,
                sensor_key=key,
                description=descriptor,
            )
        )

    if profile:
        for diagnostic_key in PROFILE_DIAGNOSTIC_KEYS:
            if diagnostic_key in SENSOR_TYPES and diagnostic_key not in keys:
                entities.append(
                    GenericObdBleSensor(
                        coordinator,
                        entry,
                        sensor_key=diagnostic_key,
                        description=SENSOR_TYPES[diagnostic_key],
                    )
                )

    async_add_entities(entities)


def _description_from_meta(
    key: str, meta: dict[str, Any] | None
) -> SensorEntityDescription:
    """Build a sensor description from optional metadata."""
    if not meta:
        return SensorEntityDescription(
            key=key,
            name=key.replace("_", " ").title(),
            icon="mdi:gauge",
        )

    device_class = None
    state_class = None

    if meta.get("device_class"):
        with_device_class = str(meta["device_class"]).upper()
        device_class = getattr(SensorDeviceClass, with_device_class, None)
    if meta.get("state_class"):
        with_state_class = str(meta["state_class"]).upper()
        state_class = getattr(SensorStateClass, with_state_class, None)

    return SensorEntityDescription(
        key=key,
        name=meta.get("name") or key.replace("_", " ").title(),
        icon=meta.get("icon", "mdi:gauge"),
        native_unit_of_measurement=meta.get("unit"),
        device_class=device_class,
        state_class=state_class,
    )


class GenericObdBleSensor(GenericObdBleEntity, SensorEntity):
    """Config entry for generic_obd_ble sensors."""

    def __init__(
        self,
        coordinator,
        config_entry,
        sensor_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._sensor = sensor_key
        self._description = description
        self._attr_name = f"{NAME} {description.name}"
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._sensor)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._description.icon
