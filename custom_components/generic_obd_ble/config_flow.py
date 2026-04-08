"""Adds config flow for Generic OBD BLE."""

from typing import Any

try:
    from bluetooth_data_tools import human_readable_name
except ImportError:  # pragma: no cover - fallback for missing dependency
    def human_readable_name(_manufacturer: str | None, name: str | None, address: str):
        """Fallback if bluetooth_data_tools is unavailable."""
        return name or address
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_SERVICE_UUID,
    CONF_CHARACTERISTIC_UUID_READ,
    CONF_CHARACTERISTIC_UUID_WRITE,
    CONF_QUERY_DTCS,
    CONF_VEHICLE_MAKE,
    CONF_VEHICLE_MODEL,
    CONF_VEHICLE_YEAR,
    CONF_VEHICLE_PROFILE_ID,
    DEFAULT_SERVICE_UUID,
    DEFAULT_CHARACTERISTIC_UUID_READ,
    DEFAULT_CHARACTERISTIC_UUID_WRITE,
    DEFAULT_VEHICLE_MAKE,
    DEFAULT_VEHICLE_MODEL,
    DEFAULT_VEHICLE_YEAR,
    DEFAULT_VEHICLE_PROFILE_ID,
)
from .profiles import find_profile_id, get_makes, get_models, get_years

GENERIC_CHOICE = "Generic"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow handler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._selected_address: str | None = None
        self._selected_title: str | None = None
        self._selected_make = DEFAULT_VEHICLE_MAKE
        self._selected_model = DEFAULT_VEHICLE_MODEL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return GenericObdBleOptionsFlowHandler()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            local_name = discovery_info.name or discovery_info.address
            self._selected_address = discovery_info.address
            self._selected_title = local_name
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return await self.async_step_vehicle_make()

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.address in self._discovered_devices
                    or not discovery.connectable
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name or 'Unknown BLE device'} "
                            f"({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_vehicle_make(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select vehicle make."""
        if user_input is not None:
            self._selected_make = user_input[CONF_VEHICLE_MAKE]
            if self._selected_make == GENERIC_CHOICE:
                return self._create_entry_for_vehicle(
                    make=DEFAULT_VEHICLE_MAKE,
                    model=DEFAULT_VEHICLE_MODEL,
                    year=DEFAULT_VEHICLE_YEAR,
                    profile_id=DEFAULT_VEHICLE_PROFILE_ID,
                )
            return await self.async_step_vehicle_model()

        make_options = [GENERIC_CHOICE, *get_makes()]
        return self.async_show_form(
            step_id="vehicle_make",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VEHICLE_MAKE,
                        default=self._selected_make,
                    ): vol.In(make_options),
                }
            ),
            errors={},
        )

    async def async_step_vehicle_model(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select vehicle model."""
        if user_input is not None:
            self._selected_model = user_input[CONF_VEHICLE_MODEL]
            if self._selected_model == GENERIC_CHOICE:
                return self._create_entry_for_vehicle(
                    make=self._selected_make,
                    model=DEFAULT_VEHICLE_MODEL,
                    year=DEFAULT_VEHICLE_YEAR,
                    profile_id=DEFAULT_VEHICLE_PROFILE_ID,
                )
            return await self.async_step_vehicle_year()

        model_options = [GENERIC_CHOICE, *get_models(self._selected_make)]
        return self.async_show_form(
            step_id="vehicle_model",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VEHICLE_MODEL,
                        default=self._selected_model,
                    ): vol.In(model_options),
                }
            ),
            errors={},
        )

    async def async_step_vehicle_year(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select vehicle year."""
        if user_input is not None:
            year = user_input[CONF_VEHICLE_YEAR]
            if year == GENERIC_CHOICE:
                profile_id = DEFAULT_VEHICLE_PROFILE_ID
            else:
                profile_id = (
                    find_profile_id(self._selected_make, self._selected_model, year)
                    or DEFAULT_VEHICLE_PROFILE_ID
                )

            return self._create_entry_for_vehicle(
                make=self._selected_make,
                model=self._selected_model,
                year=year,
                profile_id=profile_id,
            )

        year_options = [GENERIC_CHOICE, *get_years(self._selected_make, self._selected_model)]
        return self.async_show_form(
            step_id="vehicle_year",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VEHICLE_YEAR,
                        default=DEFAULT_VEHICLE_YEAR,
                    ): vol.In(year_options),
                }
            ),
            errors={},
        )

    def _create_entry_for_vehicle(
        self,
        *,
        make: str,
        model: str,
        year: str,
        profile_id: str,
    ) -> FlowResult:
        """Create config entry for selected vehicle settings."""
        return self.async_create_entry(
            title=self._selected_title or self._selected_address or DOMAIN,
            data={
                CONF_ADDRESS: self._selected_address,
                CONF_VEHICLE_MAKE: make,
                CONF_VEHICLE_MODEL: model,
                CONF_VEHICLE_YEAR: year,
                CONF_VEHICLE_PROFILE_ID: profile_id,
            },
        )


class GenericObdBleOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for generic_obd_ble."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.options: dict = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if not self.options:
            self.options = dict(self.config_entry.options)

        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VEHICLE_MAKE,
                        default=self.options.get(CONF_VEHICLE_MAKE)
                        or self.config_entry.data.get(CONF_VEHICLE_MAKE)
                        or DEFAULT_VEHICLE_MAKE,
                    ): str,
                    vol.Required(
                        CONF_VEHICLE_MODEL,
                        default=self.options.get(CONF_VEHICLE_MODEL)
                        or self.config_entry.data.get(CONF_VEHICLE_MODEL)
                        or DEFAULT_VEHICLE_MODEL,
                    ): str,
                    vol.Required(
                        CONF_VEHICLE_YEAR,
                        default=self.options.get(CONF_VEHICLE_YEAR)
                        or self.config_entry.data.get(CONF_VEHICLE_YEAR)
                        or DEFAULT_VEHICLE_YEAR,
                    ): str,
                    vol.Required(
                        CONF_VEHICLE_PROFILE_ID,
                        default=self.options.get(CONF_VEHICLE_PROFILE_ID)
                        or self.config_entry.data.get(CONF_VEHICLE_PROFILE_ID)
                        or DEFAULT_VEHICLE_PROFILE_ID,
                    ): str,
                    vol.Required(
                        "cache_values", default=self.options.get("cache_values", False)
                    ): bool,
                    vol.Required(
                        CONF_QUERY_DTCS,
                        default=self.options.get(CONF_QUERY_DTCS, True),
                    ): bool,
                    vol.Required(
                        "fast_poll", default=self.options.get("fast_poll", 10)
                    ): int,
                    vol.Required(
                        "slow_poll", default=self.options.get("slow_poll", 300)
                    ): int,
                    vol.Required(
                        "xs_poll", default=self.options.get("xs_poll", 3600)
                    ): int,
                    vol.Optional(
                        CONF_SERVICE_UUID,
                        default=self.options.get(CONF_SERVICE_UUID)
                        or DEFAULT_SERVICE_UUID,
                    ): str,
                    vol.Optional(
                        CONF_CHARACTERISTIC_UUID_READ,
                        default=self.options.get(CONF_CHARACTERISTIC_UUID_READ)
                        or DEFAULT_CHARACTERISTIC_UUID_READ,
                    ): str,
                    vol.Optional(
                        CONF_CHARACTERISTIC_UUID_WRITE,
                        default=self.options.get(CONF_CHARACTERISTIC_UUID_WRITE)
                        or DEFAULT_CHARACTERISTIC_UUID_WRITE,
                    ): str,
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_ADDRESS), data=self.options
        )
