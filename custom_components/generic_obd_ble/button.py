"""Button platform for Generic OBD BLE."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import CONF_VEHICLE_PROFILE_ID, DOMAIN, NAME
from .entity import GenericObdBleEntity
from .profiles import get_profile_by_id


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [GenericObdBleRefreshButton(coordinator, entry)]
    profile = get_profile_by_id(entry.data.get(CONF_VEHICLE_PROFILE_ID))
    if profile:
        entities.append(GenericObdBleProfileProbeButton(coordinator, entry, profile))

    async_add_entities(entities)


class GenericObdBleRefreshButton(GenericObdBleEntity, ButtonEntity):
    """Button that triggers an immediate coordinator refresh."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"
    _attr_name = f"{NAME} Refresh"

    def __init__(self, coordinator, config_entry) -> None:
        """Initialize the button."""
        super().__init__(coordinator, config_entry)

    async def async_press(self) -> None:
        """Trigger an immediate update."""
        await self.coordinator.async_request_refresh()


class GenericObdBleProfileProbeButton(GenericObdBleEntity, ButtonEntity):
    """Button that probes the selected vehicle profile."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-network-outline"

    def __init__(self, coordinator, config_entry, profile) -> None:
        """Initialize the button."""
        super().__init__(coordinator, config_entry)
        self._profile = profile
        self._attr_name = f"{NAME} Profile Probe"

    async def async_press(self) -> None:
        """Probe the selected vehicle profile and refresh state."""
        await self.coordinator.async_probe_profile()
        await self.coordinator.async_request_refresh()
