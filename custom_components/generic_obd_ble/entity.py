"""Generic OBD BLE entity base class."""

from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION


class GenericObdBleEntity(CoordinatorEntity):
    """Config entry for generic_obd_ble."""

    def __init__(self, coordinator, config_entry) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.config_entry.data[CONF_ADDRESS]}-{self.name}"

    @property
    def device_info(self):
        """Return device information."""
        adapter_name = self.coordinator.data.get("adapter_name")
        adapter_address = self.coordinator.data.get("adapter_address")
        return {
            "identifiers": {(DOMAIN, self.config_entry.data[CONF_ADDRESS])},
            "name": adapter_name or NAME,
            "model": VERSION,
            "manufacturer": "ELM327-compatible OBD adapter",
            "connections": (
                {("bluetooth", adapter_address)} if adapter_address else set()
            ),
        }
