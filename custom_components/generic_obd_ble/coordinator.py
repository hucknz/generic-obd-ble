"""Coordinator for Generic OBD BLE."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.bluetooth.api import async_address_present
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GenericObdBleApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# when the device is in range, and the car is on, poll quickly to get
# as much data as we can before it turns off
FAST_POLL_INTERVAL = timedelta(seconds=10)

# when the device is in range, but the car is off, we need to poll
# occasionally to see whether the car has be turned back on. On some cars
# this causes a relay to click every time, so this interval needs to be
# as long as possible to prevent excessive wear on the relay.
SLOW_POLL_INTERVAL = timedelta(minutes=5)

# when the device is out of range, use ultra slow polling since a bluetooth
# advertisement message will kick it back into life when back in range.
# see __init__.py: _async_specific_device_found()
ULTRA_SLOW_POLL_INTERVAL = timedelta(hours=1)

DEFAULT_FAST_POLL = 10  # pick sane defaults for your integration
DEFAULT_SLOW_POLL = 300
DEFAULT_XS_POLL = 3600
DEFAULT_CACHE_VALUES = True


class GenericObdBleDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        api: GenericObdBleApiClient,
        entry_data,
        options,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FAST_POLL_INTERVAL,
            always_update=True,
        )
        self._address = address
        self.api = api
        self._cache_data: dict[str, Any] = {}
        self._profile_probe_data: dict[str, Any] = {}
        self.entry_data = entry_data
        self.options = options

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""

        # Check if the device is still available
        _LOGGER.debug("Check if the device is still available to connect")
        available = async_address_present(self.hass, self._address, connectable=True)
        if not available:
            # Device out of range? Switch to active polling interval for when it reappears
            _LOGGER.debug("Vehicle out of range; switching to extra slow polling")
            self.update_interval = timedelta(seconds=self._xs_poll_interval)
            _LOGGER.debug(
                "Vehicle out of range; ultra slow polling interval = %s",
                self.update_interval,
            )
            if self.options.get("cache_values", False):
                return self._cache_data
            return {}

        try:
            request_config = {**self.entry_data, **self.options}
            new_data = await self.api.async_get_data(request_config)
            if new_data is None:
                raise UpdateFailed("Failed to connect to OBD device")
            if self._profile_probe_data:
                new_data.update(self._profile_probe_data)
            if len(new_data) == 0:
                # Vehicle may be asleep/off. Switch to slower polling interval.
                self.update_interval = timedelta(seconds=self._slow_poll_interval)
                _LOGGER.debug(
                    "Vehicle appears idle; slow polling interval = %s",
                    self.update_interval,
                )
            else:
                self.update_interval = timedelta(seconds=self._fast_poll_interval)
                _LOGGER.debug(
                    "Vehicle active; fast polling interval = %s",
                    self.update_interval,
                )
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err
        else:
            if self.options.get("cache_values", False):
                # Keep previous values when new payload reports None.
                # This avoids flipping entities to unavailable on transient reads.
                filtered = {
                    key: value
                    for key, value in new_data.items()
                    if value is not None
                }
                self._cache_data.update(filtered)
                return self._cache_data
            return new_data

    async def async_probe_profile(self) -> dict[str, Any]:
        """Probe the selected vehicle profile and store the summarized result."""
        request_config = {**self.entry_data, **self.options}
        probe_data = await self.api.async_probe_profile(request_config)
        self._profile_probe_data = probe_data
        self._cache_data.update(probe_data)
        return probe_data

    @property
    def options(self):
        """User configuration options."""
        return self._options

    @options.setter
    def options(self, options):
        """Set the configuration options."""
        self._options = options
        self._fast_poll_interval = options.get("fast_poll", DEFAULT_FAST_POLL)
        self._slow_poll_interval = options.get("slow_poll", DEFAULT_SLOW_POLL)
        self._xs_poll_interval = options.get("xs_poll", DEFAULT_XS_POLL)
        self._cache_values = options.get("cache_values", DEFAULT_CACHE_VALUES)

    @property
    def entry_data(self):
        """Config entry data."""
        return self._entry_data

    @entry_data.setter
    def entry_data(self, entry_data):
        """Set config entry data."""
        self._entry_data = entry_data or {}
