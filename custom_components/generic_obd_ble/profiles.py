"""Vehicle profile catalog for enhanced, make/model/year-specific entities."""

from __future__ import annotations

from typing import Any

# Base profile with standard OBD-II sensors available on most vehicles
BASE_PROFILE: dict[str, Any] = {
    "id": "base",
    "display_name": "Base OBD-II Profile",
    "description": "Standard OBD-II sensors available on most vehicles",
    "sensor_meta": {
        "engine_coolant_temp": {
            "name": "Engine coolant temperature",
            "unit": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "icon": "mdi:thermometer",
        },
        "engine_rpm": {
            "name": "Engine RPM",
            "unit": "rpm",
            "state_class": "measurement",
            "icon": "mdi:gauge",
        },
        "vehicle_speed": {
            "name": "Vehicle speed",
            "unit": "km/h",
            "device_class": "speed",
            "state_class": "measurement",
            "icon": "mdi:speedometer",
        },
        "intake_air_temp": {
            "name": "Intake air temperature",
            "unit": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "icon": "mdi:thermometer",
        },
        "maf": {
            "name": "Mass air flow",
            "unit": "g/s",
            "state_class": "measurement",
            "icon": "mdi:gauge",
        },
        "throttle_position": {
            "name": "Throttle position",
            "unit": "%",
            "state_class": "measurement",
            "icon": "mdi:percent",
        },
        "engine_runtime": {
            "name": "Engine runtime",
            "unit": "s",
            "device_class": "duration",
            "state_class": "total_increasing",
            "icon": "mdi:clock",
        },
        "fuel_level": {
            "name": "Fuel level",
            "unit": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "icon": "mdi:fuel",
        },
        "ambient_air_temp": {
            "name": "Ambient air temperature",
            "unit": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "icon": "mdi:thermometer",
        },
        "control_module_voltage": {
            "name": "Control module voltage",
            "unit": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "icon": "mdi:car-battery",
        },
    },
}

PROFILE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "nissan_leaf_ze0",
        "display_name": "Nissan Leaf ZE0 (1st Gen)",
        "make": "Nissan",
        "model": "Leaf",
        "year": "2010-2017",
        "backend": "nissan_leaf_api",
        "inherit_base_profile": False,
        "enhanced_pids": [
            {
                "key": "odometer",
                "name": "Odometer",
                "mode": "22",
                "pid": "F186",
                "decoder": {"type": "uint32", "scale": 0.1, "offset": 0.0},
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            }
        ],
        "sensor_meta": {
            "gear_position": {"name": "Gear position", "icon": "mdi:car-shift-pattern"},
            "bat_12v_voltage": {
                "name": "12V battery voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "icon": "mdi:car-battery",
            },
            "speed": {
                "name": "Vehicle speed",
                "unit": "km/h",
                "device_class": "speed",
                "state_class": "measurement",
                "icon": "mdi:speedometer",
            },
            "state_of_charge": {
                "name": "State of charge",
                "unit": "%",
                "device_class": "battery",
                "state_class": "measurement",
                "icon": "mdi:battery",
            },
            "hv_battery_health": {
                "name": "HV battery health",
                "unit": "%",
                "state_class": "measurement",
                "icon": "mdi:battery-heart",
            },
            "hv_battery_hx": {
                "name": "HV battery Hx",
                "unit": "%",
                "state_class": "measurement",
                "icon": "mdi:battery-heart-variant",
            },
            "hv_battery_Ah": {
                "name": "HV battery capacity",
                "unit": "Ah",
                "state_class": "measurement",
                "icon": "mdi:battery-lock",
            },
            "hv_battery_current_1": {
                "name": "HV battery current 1",
                "unit": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:current-dc",
            },
            "hv_battery_current_2": {
                "name": "HV battery current 2",
                "unit": "A",
                "device_class": "current",
                "state_class": "measurement",
                "icon": "mdi:current-dc",
            },
            "hv_battery_voltage": {
                "name": "HV battery voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "icon": "mdi:flash",
            },
            "odometer": {
                "name": "Odometer",
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            },
            "range_remaining": {
                "name": "Range remaining",
                "unit": "km",
                "device_class": "distance",
                "state_class": "measurement",
                "icon": "mdi:map-marker-distance",
            },
            "power_switch": {
                "name": "Power switch status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:power",
            },
            "ac_on": {
                "name": "AC status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:air-conditioner",
            },
            "rear_heater": {
                "name": "Rear heater status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:heat-wave",
            },
            "eco_mode": {
                "name": "Eco mode status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:sprout",
            },
            "e_pedal_mode": {
                "name": "e-Pedal mode status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:car-brake-low-pressure",
            },
        },
    },
    {
        "id": "nissan_leaf_ze1",
        "display_name": "Nissan Leaf ZE1 (2nd Gen)",
        "make": "Nissan",
        "model": "Leaf",
        "year": "2018-2024",
        "backend": "nissan_leaf_api",
        "inherit_base_profile": False,
        "enhanced_pids": [
            {
                "key": "odometer",
                "name": "Odometer",
                "mode": "22",
                "pid": "F186",
                "decoder": {"type": "uint32", "scale": 0.1, "offset": 0.0},
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            }
        ],
        "sensor_meta": {
            "gear_position": {"name": "Gear position", "icon": "mdi:car-shift-pattern"},
            "bat_12v_voltage": {
                "name": "12V battery voltage",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "icon": "mdi:car-battery",
            },
            "speed": {
                "name": "Vehicle speed",
                "unit": "km/h",
                "device_class": "speed",
                "state_class": "measurement",
                "icon": "mdi:speedometer",
            },
            "state_of_charge": {
                "name": "State of charge",
                "unit": "%",
                "device_class": "battery",
                "state_class": "measurement",
                "icon": "mdi:battery",
            },
            "hv_battery_health": {
                "name": "HV battery health",
                "unit": "%",
                "state_class": "measurement",
                "icon": "mdi:battery-heart",
            },
            "hv_battery_hx": {
                "name": "HV battery Hx",
                "unit": "%",
                "state_class": "measurement",
                "icon": "mdi:battery-heart-variant",
            },
            "odometer": {
                "name": "Odometer",
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            },
            "range_remaining": {
                "name": "Range remaining",
                "unit": "km",
                "device_class": "distance",
                "state_class": "measurement",
                "icon": "mdi:map-marker-distance",
            },
            "power_switch": {
                "name": "Power switch status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:power",
            },
            "ac_on": {
                "name": "AC status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:air-conditioner",
            },
            "rear_heater": {
                "name": "Rear heater status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:heat-wave",
            },
            "eco_mode": {
                "name": "Eco mode status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:sprout",
            },
            "e_pedal_mode": {
                "name": "e-Pedal mode status",
                "entity_platform": "binary_sensor",
                "icon": "mdi:car-brake-low-pressure",
            },
        },
    },
    {
        "id": "toyota_highlander_2017",
        "display_name": "Toyota Highlander (2017)",
        "make": "Toyota",
        "model": "Highlander",
        "year": "2017",
        "inherit_base_profile": True,
        "enhanced_pids": [
            {
                "key": "odometer_ecm",
                "name": "Odometer (ECM)",
                "mode": "22",
                "pid": "01A6",
                "header": "7E0",
                "decoder": {"type": "uint32", "scale": 0.1, "offset": 0.0},
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
                "icon": "mdi:counter",
            }
        ],
    },
)


def get_makes() -> list[str]:
    """Return available makes."""
    makes = {profile["make"] for profile in PROFILE_DEFINITIONS}
    return sorted(makes)


def get_models(make: str) -> list[str]:
    """Return available models for a make."""
    models = {
        profile["model"] for profile in PROFILE_DEFINITIONS if profile["make"] == make
    }
    return sorted(models)


def get_years(make: str, model: str) -> list[str]:
    """Return available years for a make/model pair."""
    years = {
        profile["year"]
        for profile in PROFILE_DEFINITIONS
        if profile["make"] == make and profile["model"] == model
    }
    return sorted(years)


def get_profile_by_id(profile_id: str | None) -> dict[str, Any] | None:
    """Return a profile by id."""
    if not profile_id or profile_id == "none":
        return None

    for profile in PROFILE_DEFINITIONS:
        if profile["id"] == profile_id:
            return profile
    return None


def get_merged_profile(profile_id: str | None) -> dict[str, Any] | None:
    """Return a profile with base profile merged in (if applicable).
    
    If the profile has inherit_base_profile=True, merges base profile data.
    Otherwise returns the profile as-is.
    """
    profile = get_profile_by_id(profile_id)
    if not profile:
        return None

    # Don't merge base profile for special backends or if explicitly disabled
    if profile.get("backend") or not profile.get("inherit_base_profile", True):
        return profile

    # Create a merged profile: base + vehicle-specific
    merged = {**profile}
    
    # Merge sensor metadata: base first, then vehicle-specific (vehicle overrides base)
    base_sensor_meta = BASE_PROFILE.get("sensor_meta", {})
    vehicle_sensor_meta = profile.get("sensor_meta", {})
    merged["sensor_meta"] = {**base_sensor_meta, **vehicle_sensor_meta}
    
    return merged


def find_profile_id(make: str, model: str, year: str) -> str | None:
    """Return profile id for a make/model/year combination."""
    for profile in PROFILE_DEFINITIONS:
        if (
            profile["make"] == make
            and profile["model"] == model
            and profile["year"] == year
        ):
            return profile["id"]
    return None
