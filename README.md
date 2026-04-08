# Generic OBD BLE - Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for reading generic OBD-II data from ELM327-style Bluetooth Low Energy adapters.

## What this integration does

- Connects to a BLE OBD adapter when it is in range.
- Sends standard Mode 01 OBD-II PID queries.
- Optionally queries Mode 03 diagnostic trouble codes (DTCs).
- Provides an optional make/model/year selector during setup.
- Exposes supported values as Home Assistant entities.

## Implemented data points

The integration currently attempts to read common generic OBD-II values such as:

- MIL status
- Confirmed DTC count
- Active DTC list (optional)
- Engine coolant temperature
- Engine RPM
- Vehicle speed
- Intake air temperature
- Ambient air temperature (if supported)
- MAF
- Throttle position
- Engine runtime
- Fuel level
- Control module voltage

Only values that are actually returned by your vehicle/adapter are created as entities.

## Vehicle Profiles

Setup now includes optional vehicle selection steps:

- Make
- Model
- Year

If a matching profile exists, the integration will query profile-specific enhanced PIDs in addition to standard OBD-II values.

Current built-in profile:

- Nissan Leaf (all years)
	- Uses the `py-nissan-leaf-obd-ble` backend for Leaf-specific data
	- Includes Leaf-specific binary entities such as `ac_on`, `eco_mode`, and `e_pedal_mode`
- Toyota Highlander (2017) - Experimental
	- [ECM] Odometer var.1

This profile is experimental and may require adapter-specific support and ECU/header compatibility.

## Installation

1. Copy [custom_components/generic_obd_ble](custom_components/generic_obd_ble) into your Home Assistant config directory under custom_components.
2. Restart Home Assistant.
3. Add integration: Settings -> Devices & Services -> Add Integration -> Generic OBD BLE.

## Configuration options

- Vehicle make/model/year/profile id
- Cache sensor values
- Query diagnostic trouble codes
- Fast / slow / extra-slow polling interval
- Service UUID
- Read characteristic UUID
- Write characteristic UUID

Default UUIDs are set for common FFE0/FFE1 ELM327 BLE adapters.

## Notes

- This integration is intentionally generic and does not include brand-specific or EV-specific proprietary PIDs.
- Different vehicles and adapters expose different subsets of standard PIDs.
- If your adapter uses custom GATT UUIDs, set them in the integration options.

## License

MIT
