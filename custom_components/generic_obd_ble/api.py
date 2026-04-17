"""Generic OBD-II over BLE client for ELM327-style adapters."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from time import monotonic
from dataclasses import dataclass
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

try:
    from py_nissan_leaf_obd_ble import NissanLeafObdBleApiClient
except ImportError:  # pragma: no cover - optional dependency at runtime
    NissanLeafObdBleApiClient = None

from .const import (
    CONF_CHARACTERISTIC_UUID_READ,
    CONF_CHARACTERISTIC_UUID_WRITE,
    CONF_QUERY_DTCS,
    CONF_VEHICLE_PROFILE_ID,
    DATA_SENSOR_META,
    DEFAULT_CHARACTERISTIC_UUID_READ,
    DEFAULT_CHARACTERISTIC_UUID_WRITE,
)
from .profiles import get_profile_by_id, get_merged_profile

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObdPid:
    """Mode 01 PID descriptor."""

    key: str
    pid: str
    decoder: Callable[[list[int]], float | int | str | None]


def _decode_pid_supported(data: list[int]) -> list[str]:
    """Decode a PID support bitmap (4 data bytes) into supported PIDs."""
    if len(data) < 4:
        return []

    supported: list[str] = []
    for byte_index, byte_val in enumerate(data[:4]):
        for bit in range(8):
            if byte_val & (1 << (7 - bit)):
                pid_num = 1 + (byte_index * 8) + bit
                supported.append(f"{pid_num:02X}")
    return supported


def _decode_mil(data: list[int]) -> bool | None:
    if len(data) < 1:
        return None
    return bool(data[0] & 0x80)


def _decode_dtc_count(data: list[int]) -> int | None:
    if len(data) < 1:
        return None
    return data[0] & 0x7F


def _decode_temp(data: list[int]) -> float | None:
    if len(data) < 1:
        return None
    return float(data[0] - 40)


def _decode_rpm(data: list[int]) -> float | None:
    if len(data) < 2:
        return None
    return float(((data[0] * 256) + data[1]) / 4)


def _decode_speed(data: list[int]) -> int | None:
    if len(data) < 1:
        return None
    return int(data[0])


def _decode_runtime(data: list[int]) -> int | None:
    if len(data) < 2:
        return None
    return int((data[0] * 256) + data[1])


def _decode_maf(data: list[int]) -> float | None:
    if len(data) < 2:
        return None
    return float(((data[0] * 256) + data[1]) / 100)


def _decode_percent(data: list[int]) -> float | None:
    if len(data) < 1:
        return None
    return float((data[0] * 100) / 255)


def _decode_voltage(data: list[int]) -> float | None:
    if len(data) < 2:
        return None
    return float(((data[0] * 256) + data[1]) / 1000)


def _decode_profile_value(payload: list[int], decoder_cfg: dict[str, Any]) -> float | int | None:
    """Decode a profile PID payload using a simple declarative decoder schema."""
    decoder_type = decoder_cfg.get("type", "uint16")
    start = int(decoder_cfg.get("byte_start", 0))
    length = int(decoder_cfg.get("length", 2 if decoder_type == "uint16" else 4))

    if len(payload) < start + length:
        return None

    raw_bytes = payload[start : start + length]
    raw_int = int.from_bytes(raw_bytes, byteorder="big", signed=False)

    if decoder_type in {"uint16", "uint32"}:
        scale = float(decoder_cfg.get("scale", 1.0))
        offset = float(decoder_cfg.get("offset", 0.0))
        return (raw_int * scale) + offset

    if decoder_type == "linear":
        scale = float(decoder_cfg.get("scale", 1.0))
        offset = float(decoder_cfg.get("offset", 0.0))
        return (raw_int * scale) + offset

    return None


def _normalize_leaf_soc(value: object, profile_id: str | None) -> float | None:
    """Normalize Leaf SoC to a percentage in the range 0..100."""
    if not isinstance(value, (int, float)):
        return None

    soc = float(value)
    if 0 <= soc <= 100:
        return soc

    # Different adapters/libraries expose SoC in different scales.
    divisors: tuple[float, ...]
    if profile_id == "nissan_leaf_ze0":
        divisors = (4.096, 21.64, 10.0, 100.0, 102.4, 1000.0)
    else:
        divisors = (21.64, 10.0, 100.0, 4.096, 102.4, 1000.0)

    normalized_candidates = [
        soc / divisor for divisor in divisors if 0 <= (soc / divisor) <= 100
    ]
    if not normalized_candidates:
        return None

    # Prefer the most plausible percentage from available scales.
    return max(normalized_candidates)


def _extract_leaf_soc(leaf_data: dict[str, object], profile_id: str | None) -> float | None:
    """Extract and normalize Leaf SoC from known backend field aliases."""
    soc_candidates = (
        "state_of_charge",
        "soc",
        "soc_percent",
        "soc_pct",
        "battery_soc",
        "dash_soc",
        "dashboard_soc",
    )
    for key in soc_candidates:
        normalized = _normalize_leaf_soc(leaf_data.get(key), profile_id)
        if normalized is not None:
            return normalized
    return None


def _normalize_leaf_ahr(value: object) -> float | None:
    """Normalize Leaf Ah reading to a plausible range."""
    if not isinstance(value, (int, float)):
        return None

    ahr = float(value)
    if 20 <= ahr <= 140:
        return ahr

    divisors = (25.6, 21.64, 10.0, 100.0, 1024.0)
    candidates = [ahr / divisor for divisor in divisors if 20 <= (ahr / divisor) <= 140]
    if not candidates:
        return None

    # Prefer lower plausible value when multiple scales fit.
    return min(candidates)


def _extract_leaf_ahr(leaf_data: dict[str, object]) -> float | None:
    """Extract and normalize Leaf Ah from known backend field aliases."""
    candidates = (
        "hv_battery_Ah",
        "hv_battery_ah",
        "battery_ahr",
        "ahr",
    )
    for key in candidates:
        normalized = _normalize_leaf_ahr(leaf_data.get(key))
        if normalized is not None:
            return normalized
    return None


def _derive_leaf_soh_from_ahr(ahr: float | None, profile_id: str | None) -> float | None:
    """Estimate SOH% from Ah using nominal pack Ah by profile generation."""
    if ahr is None or ahr <= 0:
        return None

    nominal_ahr = 79.2 if profile_id == "nissan_leaf_ze0" else 115.0
    soh = (ahr / nominal_ahr) * 100.0
    if 0 <= soh <= 100:
        return soh
    return None


def _normalize_leaf_percent(value: object) -> float | None:
    """Normalize a percentage-like value to 0..100."""
    if not isinstance(value, (int, float)):
        return None

    v = float(value)
    if 0 <= v <= 100:
        return v

    divisors = (1024.0, 100.0, 21.64, 10.0)
    candidates = [v / divisor for divisor in divisors if 0 <= (v / divisor) <= 100]
    if not candidates:
        return None
    return max(candidates)


def _extract_leaf_soh(leaf_data: dict[str, object], profile_id: str | None) -> float | None:
    """Extract and normalize Leaf SOH from known backend aliases."""
    soh_candidates = (
        "hv_battery_health",
        "soh",
        "battery_soh",
    )

    for key in soh_candidates:
        normalized = _normalize_leaf_percent(leaf_data.get(key))
        if normalized is not None and normalized >= 10:
            return normalized

    # Fallback when raw SOH is implausibly tiny: derive from Ah.
    return _derive_leaf_soh_from_ahr(_extract_leaf_ahr(leaf_data), profile_id)


def _extract_leaf_hx(leaf_data: dict[str, object]) -> float | None:
    """Extract and normalize Leaf Hx from known backend aliases."""
    hx_candidates = (
        "hx",
        "h_x",
        "battery_hx",
        "hv_battery_hx",
    )
    for key in hx_candidates:
        normalized = _normalize_leaf_percent(leaf_data.get(key))
        if normalized is not None:
            return normalized
    return None


def _extract_leaf_odometer(leaf_data: dict[str, object]) -> float | None:
    """Extract odometer from Leaf backend keys and normalize to kilometers."""
    km_candidates = (
        "odometer",
        "odometer_km",
        "odometer_kilometers",
        "odo",
        "odo_km",
        "distance_total_km",
    )
    km_values: list[float] = []
    for key in km_candidates:
        value = leaf_data.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            km_values.append(float(value))

    miles_candidates = (
        "odometer_miles",
        "odo_miles",
        "distance_total_miles",
    )
    km_from_miles: list[float] = []
    for key in miles_candidates:
        value = leaf_data.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            km_from_miles.append(float(value) * 1.609344)

    non_zero = [value for value in [*km_values, *km_from_miles] if value > 0]
    if non_zero:
        return max(non_zero)

    if km_values or km_from_miles:
        return 0.0

    return None


def _parse_leaf_odometer_response(raw: str) -> float | None:
    """Parse raw ELM327 response for Leaf odometer (22 0E01)."""
    filtered = "".join(ch for ch in raw.upper() if ch in "0123456789ABCDEF")
    if len(filtered) < 6:
        return None

    # Build 2-hex-digit tokens from fully filtered payload.
    if len(filtered) % 2 != 0:
        filtered = filtered[:-1]
    tokens = [filtered[i : i + 2] for i in range(0, len(filtered), 2)]

    # Expected positive response is 62 0E 01 xx xx xx
    for i in range(len(tokens) - 5):
        if tokens[i : i + 3] == ["62", "0E", "01"]:
            try:
                b1 = int(tokens[i + 3], 16)
                b2 = int(tokens[i + 4], 16)
                b3 = int(tokens[i + 5], 16)
            except ValueError:
                return None
            return float((b1 << 16) | (b2 << 8) | b3)

    # Header + PCI form can include: 76 30 66 20 E0 1x xx xx ... depending on formatting.
    # Retry on a compact stream by searching for 0E 01 and taking next 3 bytes.
    for i in range(len(tokens) - 4):
        if tokens[i : i + 2] == ["0E", "01"]:
            try:
                b1 = int(tokens[i + 2], 16)
                b2 = int(tokens[i + 3], 16)
                b3 = int(tokens[i + 4], 16)
            except ValueError:
                return None
            return float((b1 << 16) | (b2 << 8) | b3)

    return None


PID_DEFINITIONS: tuple[ObdPid, ...] = (
    ObdPid("engine_coolant_temp", "05", _decode_temp),
    ObdPid("engine_rpm", "0C", _decode_rpm),
    ObdPid("vehicle_speed", "0D", _decode_speed),
    ObdPid("intake_air_temp", "0F", _decode_temp),
    ObdPid("maf", "10", _decode_maf),
    ObdPid("throttle_position", "11", _decode_percent),
    ObdPid("engine_runtime", "1F", _decode_runtime),
    ObdPid("fuel_level", "2F", _decode_percent),
    ObdPid("ambient_air_temp", "46", _decode_temp),
    ObdPid("control_module_voltage", "42", _decode_voltage),
)


class GenericObdBleApiClient:
    """Fetch generic OBD-II values from an ELM327-style BLE adapter."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._leaf_odometer_cache: float | None = None
        self._leaf_odometer_last_attempt: float = 0.0

    async def async_get_data(self, options: dict) -> dict[str, object]:
        """Fetch standard and profile-enhanced OBD-II values."""
        profile = get_profile_by_id(options.get(CONF_VEHICLE_PROFILE_ID))
        if profile and profile.get("backend") == "nissan_leaf_api":
            return await self._async_get_nissan_leaf_data(options, profile)

        read_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_READ,
            DEFAULT_CHARACTERISTIC_UUID_READ,
        )
        write_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_WRITE,
            DEFAULT_CHARACTERISTIC_UUID_WRITE,
        )

        response: dict[str, object] = {
            "adapter_name": self._ble_device.name or "ELM327",
            "adapter_address": self._ble_device.address,
            DATA_SENSOR_META: {},
        }

        if profile:
            response["vehicle_profile"] = profile["display_name"]
            # Use merged profile to get base + vehicle-specific sensor metadata
            merged_profile = get_merged_profile(options.get(CONF_VEHICLE_PROFILE_ID))
            if merged_profile:
                response[DATA_SENSOR_META] = dict(merged_profile.get("sensor_meta", {}))

        client: BleakClient | None = None
        try:
            client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=2,
            )

            await self._initialize_adapter(client, read_uuid, write_uuid)

            supported_pids = await self._get_supported_pids(client, read_uuid, write_uuid)
            response["supported_pids"] = sorted(supported_pids)

            monitor_status = await self._query_pid(
                client,
                read_uuid,
                write_uuid,
                mode="01",
                pid="01",
            )
            if monitor_status is not None:
                response["mil_on"] = _decode_mil(monitor_status)
                response["confirmed_dtc_count"] = _decode_dtc_count(monitor_status)

            for definition in PID_DEFINITIONS:
                if supported_pids and definition.pid not in supported_pids:
                    continue

                payload = await self._query_pid(
                    client,
                    read_uuid,
                    write_uuid,
                    mode="01",
                    pid=definition.pid,
                )
                if payload is None:
                    continue

                value = definition.decoder(payload)
                if value is not None:
                    response[definition.key] = value

            if options.get(CONF_QUERY_DTCS, True):
                dtcs = await self._query_dtcs(client, read_uuid, write_uuid)
                if dtcs is not None:
                    response["active_dtcs"] = ",".join(dtcs) if dtcs else "none"

            if profile:
                await self._query_profile_pids(
                    client,
                    read_uuid,
                    write_uuid,
                    profile,
                    response,
                )
        except (BleakError, TimeoutError, ValueError) as err:
            _LOGGER.debug("OBD BLE polling failed: %s", err)
            return {}
        finally:
            if client:
                with contextlib.suppress(BleakError):
                    await client.disconnect()

        if not response[DATA_SENSOR_META]:
            response.pop(DATA_SENSOR_META)

        return response

    async def _async_get_nissan_leaf_data(
        self,
        options: dict,
        profile: dict[str, Any],
    ) -> dict[str, object]:
        """Fetch Nissan Leaf data via the dedicated Leaf library."""
        response: dict[str, object] = {
            "adapter_name": self._ble_device.name or "ELM327",
            "adapter_address": self._ble_device.address,
            "vehicle_profile": profile["display_name"],
            DATA_SENSOR_META: dict(profile.get("sensor_meta", {})),
        }

        if NissanLeafObdBleApiClient is None:
            response["leaf_backend_status"] = "py-nissan-leaf-obd-ble is not installed"
            return response

        try:
            leaf_client = NissanLeafObdBleApiClient(self._ble_device)
            leaf_data = await leaf_client.async_get_data(options)
        except Exception as err:  # pragma: no cover - depends on runtime BLE state
            _LOGGER.debug("Nissan Leaf backend polling failed: %s", err)
            response["leaf_backend_status"] = f"Leaf backend error: {err}"
            return response

        if not leaf_data:
            response["leaf_backend_status"] = "Leaf backend returned no data"
            return response

        _LOGGER.debug(
            "Leaf raw metrics: %s",
            {
                key: leaf_data.get(key)
                for key in (
                    "state_of_charge",
                    "soc",
                    "hv_battery_Ah",
                    "hv_battery_health",
                    "hx",
                    "odometer",
                    "odometer_km",
                    "odometer_miles",
                )
                if key in leaf_data
            },
        )

        normalized_soc = _extract_leaf_soc(leaf_data, profile.get("id"))
        if normalized_soc is not None:
            original_soc = leaf_data.get("state_of_charge")
            if original_soc != normalized_soc:
                _LOGGER.debug(
                    "Normalized Leaf SoC from %s to %.3f for profile %s",
                    original_soc,
                    normalized_soc,
                    profile.get("id", "unknown"),
                )
                leaf_data["state_of_charge"] = round(normalized_soc, 3)
        elif isinstance(leaf_data.get("state_of_charge"), (int, float)):
            # Avoid exposing implausible raw values as percentages.
            leaf_data.pop("state_of_charge", None)

        normalized_ahr = _extract_leaf_ahr(leaf_data)
        if normalized_ahr is not None:
            leaf_data["hv_battery_Ah"] = round(normalized_ahr, 3)

        normalized_soh = _extract_leaf_soh(leaf_data, profile.get("id"))
        if normalized_soh is not None:
            leaf_data["hv_battery_health"] = round(normalized_soh, 3)

        normalized_hx = _extract_leaf_hx(leaf_data)
        if normalized_hx is not None:
            leaf_data["hv_battery_hx"] = round(normalized_hx, 3)
            sensor_meta = response.get(DATA_SENSOR_META)
            if isinstance(sensor_meta, dict) and "hv_battery_hx" not in sensor_meta:
                sensor_meta["hv_battery_hx"] = {
                    "name": "HV battery Hx",
                    "unit": "%",
                    "state_class": "measurement",
                    "icon": "mdi:battery-heart-variant",
                }

        _LOGGER.debug(
            "Leaf normalized metrics: %s",
            {
                "state_of_charge": leaf_data.get("state_of_charge"),
                "hv_battery_Ah": leaf_data.get("hv_battery_Ah"),
                "hv_battery_health": leaf_data.get("hv_battery_health"),
                "hv_battery_hx": leaf_data.get("hv_battery_hx"),
            },
        )

        response.update(leaf_data)

        odometer = _extract_leaf_odometer(leaf_data)
        odometer_source = "leaf_backend"
        if odometer is None or odometer <= 0:
            fallback_odometer = await self._async_query_leaf_odometer_fallback(options)
            if fallback_odometer is not None:
                odometer = fallback_odometer
                odometer_source = "fallback_query"

        if odometer is not None and odometer > 0:
            response["odometer"] = round(odometer, 3)
            self._leaf_odometer_cache = odometer
        elif self._leaf_odometer_cache is not None and self._leaf_odometer_cache > 0:
            # Reuse last known good odometer instead of exposing transient zero.
            response["odometer"] = round(self._leaf_odometer_cache, 3)
            odometer_source = "cached"

        _LOGGER.debug(
            "Leaf odometer resolved: value=%s source=%s raw_backend=%s",
            response.get("odometer"),
            odometer_source,
            leaf_data.get("odometer"),
        )

        response["leaf_backend_status"] = "Leaf backend active"
        return response

    async def _async_query_leaf_odometer_fallback(self, options: dict) -> float | None:
        """Fallback Leaf odometer read using 22 0E01 on header 743."""
        now = monotonic()
        # Throttle only after we have a cached value; otherwise keep trying.
        if (
            self._leaf_odometer_cache is not None
            and now - self._leaf_odometer_last_attempt < 300
        ):
            _LOGGER.debug("Leaf odometer fallback throttled; using cache=%s", self._leaf_odometer_cache)
            return self._leaf_odometer_cache

        self._leaf_odometer_last_attempt = now

        read_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_READ,
            DEFAULT_CHARACTERISTIC_UUID_READ,
        )
        write_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_WRITE,
            DEFAULT_CHARACTERISTIC_UUID_WRITE,
        )

        client: BleakClient | None = None
        try:
            client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=2,
            )
            # Match py_nissan_leaf_obd_ble startup for framed CAN commands.
            await self._send_command(client, read_uuid, write_uuid, "ATE0")
            await self._send_command(client, read_uuid, write_uuid, "ATSP6")
            await self._send_command(client, read_uuid, write_uuid, "ATH1")
            await self._send_command(client, read_uuid, write_uuid, "ATL0")
            await self._send_command(client, read_uuid, write_uuid, "ATS0")
            await self._send_command(client, read_uuid, write_uuid, "ATCAF0")

            for header in ("743", "79B", "797"):
                for pid in ("0E01", "F186"):
                    await self._send_command(client, read_uuid, write_uuid, f"AT SH {header}")
                    await self._send_command(client, read_uuid, write_uuid, f"AT FC SH {header}")
                    await self._send_command(client, read_uuid, write_uuid, "AT FC SD 30 00 00")
                    await self._send_command(client, read_uuid, write_uuid, "AT FC SM 1")

                    raw = await self._send_command(client, read_uuid, write_uuid, f"03 22 {pid[:2]} {pid[2:]}")
                    parsed = _parse_leaf_odometer_response(raw)
                    _LOGGER.debug(
                        "Leaf odometer fallback raw response: header=%s pid=%s raw=%s parsed=%s",
                        header,
                        pid,
                        raw,
                        parsed,
                    )
                    if parsed is not None and parsed > 0:
                        self._leaf_odometer_cache = parsed
                        return self._leaf_odometer_cache

            return self._leaf_odometer_cache
        except (BleakError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Leaf odometer fallback query failed: %s", err)
            return self._leaf_odometer_cache
        finally:
            if client:
                with contextlib.suppress(BleakError):
                    await client.disconnect()

    async def async_probe_profile(self, options: dict) -> dict[str, object]:
        """Probe the selected vehicle profile and summarize supported enhanced PIDs."""
        profile = get_profile_by_id(options.get(CONF_VEHICLE_PROFILE_ID))
        if not profile:
            return {
                "profile_probe_status": "No vehicle profile selected",
                "profile_probe_supported_count": 0,
                "profile_probe_supported_entities": "none",
                "profile_probe_unsupported_entities": "none",
            }

        if profile.get("backend") == "nissan_leaf_api":
            leaf_data = await self._async_get_nissan_leaf_data(options, profile)
            discovered = [
                key
                for key in leaf_data.keys()
                if key
                not in {
                    "adapter_name",
                    "adapter_address",
                    "vehicle_profile",
                    "leaf_backend_status",
                    DATA_SENSOR_META,
                }
            ]
            return {
                "profile_probe_status": f"Leaf profile probe complete: {len(discovered)} keys",
                "profile_probe_supported_count": len(discovered),
                "profile_probe_supported_entities": ", ".join(sorted(discovered)) if discovered else "none",
                "profile_probe_unsupported_entities": "none",
            }

        read_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_READ,
            DEFAULT_CHARACTERISTIC_UUID_READ,
        )
        write_uuid = options.get(
            CONF_CHARACTERISTIC_UUID_WRITE,
            DEFAULT_CHARACTERISTIC_UUID_WRITE,
        )

        client: BleakClient | None = None
        supported: list[str] = []
        unsupported: list[str] = []

        try:
            client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=2,
            )
            await self._initialize_adapter(client, read_uuid, write_uuid)
            probe_result = await self._probe_profile_pids(
                client,
                read_uuid,
                write_uuid,
                profile,
            )
            supported = probe_result["supported"]
            unsupported = probe_result["unsupported"]
            
            # Add base profile sensor metadata to the list of supported if profile inherits from base
            merged_profile = get_merged_profile(options.get(CONF_VEHICLE_PROFILE_ID))
            if merged_profile and merged_profile.get("inherit_base_profile", True):
                base_sensors = list(merged_profile.get("sensor_meta", {}).keys())
                # These are standard OBD-II sensors that should be listed as "supported by base profile"
                for sensor_key in base_sensors:
                    if sensor_key not in supported and sensor_key not in [pid.key for pid in PID_DEFINITIONS]:
                        # Mark as supported from base profile
                        supported.insert(0, f"[base] {sensor_key}")
                        
        except (BleakError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Profile probe failed: %s", err)
            return {
                "profile_probe_status": f"Profile probe failed: {err}",
                "profile_probe_supported_count": 0,
                "profile_probe_supported_entities": "none",
                "profile_probe_unsupported_entities": "none",
            }
        finally:
            if client:
                with contextlib.suppress(BleakError):
                    await client.disconnect()

        return {
            "profile_probe_status": f"Profile probe complete: {len(supported)} supported, {len(unsupported)} unsupported",
            "profile_probe_supported_count": len(supported),
            "profile_probe_supported_entities": ", ".join(supported) if supported else "none",
            "profile_probe_unsupported_entities": ", ".join(unsupported) if unsupported else "none",
        }

    async def _query_profile_pids(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
        profile: dict[str, Any],
        response: dict[str, object],
    ) -> None:
        """Query profile-enhanced PIDs for the selected vehicle profile."""
        # Get reference to sensor metadata dict, ensuring it's a proper dict
        sensor_meta = response.get(DATA_SENSOR_META)
        if not isinstance(sensor_meta, dict):
            sensor_meta = {}
            response[DATA_SENSOR_META] = sensor_meta
            
        for profile_pid in profile.get("enhanced_pids", []):
            header = profile_pid.get("header")
            if header:
                await self._send_command(client, read_uuid, write_uuid, f"ATSH{header}")

            payload = await self._query_pid(
                client,
                read_uuid,
                write_uuid,
                mode=profile_pid["mode"],
                pid=profile_pid["pid"],
            )

            if header:
                await self._send_command(client, read_uuid, write_uuid, "ATSH7DF")

            if payload is None:
                continue

            decoded_value = _decode_profile_value(payload, profile_pid.get("decoder", {}))
            if decoded_value is None:
                continue

            key = profile_pid["key"]
            response[key] = decoded_value
            sensor_meta[key] = {
                "name": profile_pid.get("name", key.replace("_", " ").title()),
                "unit": profile_pid.get("unit"),
                "device_class": profile_pid.get("device_class"),
                "state_class": profile_pid.get("state_class"),
                "icon": profile_pid.get("icon", "mdi:gauge"),
            }

    async def _probe_profile_pids(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
        profile: dict[str, Any],
    ) -> dict[str, list[str]]:
        """Check which enhanced PIDs in a profile actually respond."""
        supported: list[str] = []
        unsupported: list[str] = []

        for profile_pid in profile.get("enhanced_pids", []):
            header = profile_pid.get("header")
            if header:
                await self._send_command(client, read_uuid, write_uuid, f"ATSH{header}")

            payload = await self._query_pid(
                client,
                read_uuid,
                write_uuid,
                mode=profile_pid["mode"],
                pid=profile_pid["pid"],
            )

            if header:
                await self._send_command(client, read_uuid, write_uuid, "ATSH7DF")

            if payload is None:
                unsupported.append(profile_pid.get("name", profile_pid["key"]))
                continue

            supported.append(profile_pid.get("name", profile_pid["key"]))

        return {"supported": supported, "unsupported": unsupported}

    async def _initialize_adapter(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
    ) -> None:
        """Send standard ELM327 initialization commands."""
        await self._send_command(client, read_uuid, write_uuid, "ATZ")
        await self._send_command(client, read_uuid, write_uuid, "ATE0")
        await self._send_command(client, read_uuid, write_uuid, "ATL0")
        await self._send_command(client, read_uuid, write_uuid, "ATS0")
        await self._send_command(client, read_uuid, write_uuid, "ATH0")
        await self._send_command(client, read_uuid, write_uuid, "ATSP0")

    async def _get_supported_pids(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
    ) -> set[str]:
        """Read supported PID pages from 00/20/40/60."""
        supported: set[str] = set()
        page_bases = ["00", "20", "40", "60"]

        for page in page_bases:
            payload = await self._query_pid(
                client,
                read_uuid,
                write_uuid,
                mode="01",
                pid=page,
            )
            if payload is None:
                continue

            page_supported = _decode_pid_supported(payload)
            base = int(page, 16)
            for pid_hex in page_supported:
                supported.add(f"{base + int(pid_hex, 16):02X}")

            # If PID xx20 is not marked as supported, there are no more pages.
            if len(payload) < 4 or (payload[3] & 0x01) == 0:
                break

        return supported

    async def _query_pid(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
        *,
        mode: str,
        pid: str,
    ) -> list[int] | None:
        """Query a mode/pid command and return payload data bytes."""
        command = f"{mode}{pid}"
        raw = await self._send_command(client, read_uuid, write_uuid, command)
        if not raw or "NO DATA" in raw or "STOPPED" in raw:
            return None

        mode_response = f"{int(mode, 16) + 0x40:02X}"
        pid_tokens = [pid[i : i + 2].upper() for i in range(0, len(pid), 2)]
        tokens = [
            token.upper()
            for token in raw.replace("\r", " ").replace("\n", " ").split(" ")
            if token
        ]

        prefix = [mode_response, *pid_tokens]

        for index in range(len(tokens) - len(prefix) + 1):
            if tokens[index : index + len(prefix)] != prefix:
                continue

            data_tokens: list[int] = []
            for token in tokens[index + len(prefix) :]:
                if len(token) != 2:
                    break
                try:
                    data_tokens.append(int(token, 16))
                except ValueError:
                    break
            return data_tokens

        return None

    async def _query_dtcs(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
    ) -> list[str] | None:
        """Query confirmed diagnostic trouble codes (Mode 03)."""
        raw = await self._send_command(client, read_uuid, write_uuid, "03")
        if not raw:
            return None
        if "NO DATA" in raw:
            return []

        tokens = [tok for tok in raw.replace("\r", " ").replace("\n", " ").split(" ") if tok]
        try:
            start = tokens.index("43") + 1
        except ValueError:
            return None

        code_bytes: list[int] = []
        for token in tokens[start:]:
            if len(token) != 2:
                break
            try:
                code_bytes.append(int(token, 16))
            except ValueError:
                break

        dtcs: list[str] = []
        for idx in range(0, len(code_bytes) - 1, 2):
            first = code_bytes[idx]
            second = code_bytes[idx + 1]
            if first == 0 and second == 0:
                continue
            dtcs.append(self._format_dtc(first, second))
        return dtcs

    @staticmethod
    def _format_dtc(first: int, second: int) -> str:
        family = ["P", "C", "B", "U"][(first & 0xC0) >> 6]
        digit1 = (first & 0x30) >> 4
        digit2 = first & 0x0F
        return f"{family}{digit1}{digit2:X}{second:02X}"

    async def _send_command(
        self,
        client: BleakClient,
        read_uuid: str,
        write_uuid: str,
        command: str,
    ) -> str:
        """Send one ELM327 command and return full text until prompt character."""
        chunks: list[str] = []
        response_done = asyncio.Event()

        def _notification_handler(_char: int, data: bytearray) -> None:
            text = data.decode("ascii", errors="ignore")
            chunks.append(text)
            if ">" in text:
                response_done.set()

        await client.start_notify(read_uuid, _notification_handler)
        try:
            await client.write_gatt_char(
                write_uuid,
                f"{command}\r".encode("ascii"),
                response=True,
            )
            await asyncio.wait_for(response_done.wait(), timeout=4.0)
        finally:
            with contextlib.suppress(BleakError):
                await client.stop_notify(read_uuid)

        raw = "".join(chunks).replace(">", " ").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        filtered = [line for line in lines if line != command and line != "SEARCHING..."]
        return " ".join(filtered)
