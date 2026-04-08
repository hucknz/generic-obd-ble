"""Vehicle profile catalog for enhanced, make/model/year-specific entities."""

from __future__ import annotations

from typing import Any

PROFILE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "toyota_highlander_2017",
        "display_name": "Toyota Highlander (2017) - Experimental",
        "make": "Toyota",
        "model": "Highlander",
        "year": "2017",
        "enhanced_pids": [
            {
                "key": "odometer_ecm_var_1",
                "name": "[ECM] Odometer var.1",
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
