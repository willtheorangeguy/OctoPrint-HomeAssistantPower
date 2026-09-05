# coding=utf-8
"""Power and energy sensor handling.

Energy-monitoring smart plugs expose their readings as *separate* Home
Assistant sensor entities alongside the switch (``switch.printer_plug`` plus
``sensor.printer_plug_power`` and ``sensor.printer_plug_energy``), so this
module deals with linking them, normalising units, and turning a cumulative
energy meter into a per-print consumption figure.
"""

from __future__ import absolute_import, unicode_literals

import errno
import json
import logging
import os
import time

# Multipliers converting a sensor reading into the canonical unit.
_POWER_TO_W = {"w": 1.0, "watt": 1.0, "kw": 1000.0, "mw": 0.001, "milliwatt": 0.001}
_ENERGY_TO_KWH = {"kwh": 1.0, "wh": 0.001, "mwh": 1000.0}

# Suffixes we look for when guessing which sensors belong to a switch. Ordered:
# the first match wins, so the most specific/common naming comes first.
_POWER_SUFFIXES = (
    "_power",
    "_active_power",
    "_current_power",
    "_power_w",
    "_electric_consumption_w",
)
_ENERGY_SUFFIXES = (
    "_energy",
    "_total_energy",
    "_energy_total",
    "_summation_delivered",
    "_electric_consumption_kwh",
)

# ``state_class`` values that make a running total meaningful. A plain
# ``measurement`` sensor is an instantaneous reading; differencing it would
# produce a number that looks plausible and is wrong.
CUMULATIVE_STATE_CLASSES = ("total_increasing", "total")

# Values Home Assistant uses for "no reading right now".
_NON_VALUES = ("unavailable", "unknown", "none", "")

_HISTORY_FILE = "energy_history.json"
_HISTORY_LIMIT = 25


def _attr(state, name, default=None):
    if not isinstance(state, dict):
        return default
    return (state.get("attributes") or {}).get(name, default)


def _numeric_state(state):
    """Return the sensor value as a float, or ``None`` if it has no reading."""
    if not isinstance(state, dict):
        return None
    raw = state.get("state")
    if raw is None or str(raw).strip().lower() in _NON_VALUES:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_power(state):
    """Return the reading in watts, or ``None``.

    An unrecognised unit returns ``None`` rather than a guess -- showing no
    number is better than showing one that is off by 1000x.
    """
    value = _numeric_state(state)
    if value is None:
        return None
    unit = str(_attr(state, "unit_of_measurement", "W") or "W").strip().lower()
    factor = _POWER_TO_W.get(unit)
    if factor is None:
        return None
    return value * factor


def parse_energy(state):
    """Return the reading in kWh, or ``None``."""
    value = _numeric_state(state)
    if value is None:
        return None
    unit = str(_attr(state, "unit_of_measurement", "kWh") or "kWh").strip().lower()
    factor = _ENERGY_TO_KWH.get(unit)
    if factor is None:
        return None
    return value * factor


def is_cumulative(state):
    """True if this energy sensor is a meter that can be differenced.

    Sensors with no ``state_class`` at all are treated as cumulative: plenty of
    Zigbee2MQTT and template sensors omit it while still being real meters, and
    the reset guard in :class:`EnergyTracker` catches the rest.
    """
    state_class = _attr(state, "state_class")
    if state_class is None:
        return True
    return str(state_class).strip().lower() in CUMULATIVE_STATE_CLASSES


def detect_sensors(entity_id, all_states):
    """Guess the power and energy sensors belonging to ``entity_id``.

    Matches on the entity ID stem first (``switch.printer_plug`` ->
    ``sensor.printer_plug_power``), then falls back to comparing friendly-name
    prefixes with a device-class check. Naming varies between ZHA, Zigbee2MQTT
    and DIRIGERA, so this is a convenience only -- the settings dialog always
    allows setting both sensors by hand.
    """
    result = {"power_sensor": None, "energy_sensor": None}
    if not entity_id or "." not in entity_id or not all_states:
        return result

    stem = entity_id.split(".", 1)[1]
    sensors = {
        sensor_id: state
        for sensor_id, state in all_states.items()
        if sensor_id.startswith("sensor.")
    }

    for key, suffixes in (
        ("power_sensor", _POWER_SUFFIXES),
        ("energy_sensor", _ENERGY_SUFFIXES),
    ):
        for suffix in suffixes:
            candidate = "sensor.{}{}".format(stem, suffix)
            if candidate in sensors:
                result[key] = candidate
                break

    # Fall back to friendly names, e.g. switch "Printer Plug" alongside sensor
    # "Printer Plug Power" whose entity IDs do not share a stem.
    switch_name = _attr(all_states.get(entity_id), "friendly_name")
    if switch_name:
        prefix = switch_name.strip().lower()
        for key, device_class in (
            ("power_sensor", "power"),
            ("energy_sensor", "energy"),
        ):
            if result[key]:
                continue
            for sensor_id, state in sensors.items():
                name = str(_attr(state, "friendly_name", "") or "").strip().lower()
                if not name.startswith(prefix):
                    continue
                if str(_attr(state, "device_class", "") or "").lower() == device_class:
                    result[key] = sensor_id
                    break

    return result


class EnergyTracker(object):
    """Tracks how much energy each print consumed.

    Takes a snapshot of the cumulative meter when a print starts and again when
    it ends; the difference is what the print used. Results are persisted to the
    plugin data folder so a restart does not lose the history.
    """

    def __init__(self, data_folder, logger=None):
        self._data_folder = data_folder
        self._logger = logger or logging.getLogger(__name__)
        self._history = []
        self._active = None
        self._load()

    # ---------------------------------------------------------------- lifecycle

    def start_print(self, name, energy_kwh, cumulative=True):
        """Record the meter reading at the start of a print."""
        if energy_kwh is None or not cumulative:
            # Without a usable cumulative meter there is nothing to difference,
            # so track nothing rather than report a made-up number.
            self._active = None
            return
        self._active = {
            "name": name,
            "started": time.time(),
            "start_kwh": energy_kwh,
        }

    def finish_print(self, outcome, energy_kwh):
        """Close out the active print and return its record, or ``None``."""
        active = self._active
        self._active = None
        if not active or energy_kwh is None:
            return None

        delta = energy_kwh - active["start_kwh"]
        if delta < 0:
            # The meter was reset (plug re-paired, integration reloaded, daily
            # utility meter rollover). The measurement is unusable.
            self._logger.info(
                "Energy meter decreased during the print; discarding the reading."
            )
            return None

        record = {
            "name": active["name"],
            "outcome": outcome,
            "started": active["started"],
            "finished": time.time(),
            "kwh": round(delta, 4),
        }
        self._history.insert(0, record)
        del self._history[_HISTORY_LIMIT:]
        self._save()
        return record

    def abandon(self):
        """Drop the active measurement without recording it."""
        self._active = None

    # ------------------------------------------------------------------ reading

    def current_kwh(self, energy_kwh):
        """Energy used by the in-progress print so far, or ``None``."""
        if not self._active or energy_kwh is None:
            return None
        delta = energy_kwh - self._active["start_kwh"]
        if delta < 0:
            return None
        return round(delta, 4)

    @property
    def tracking(self):
        return self._active is not None

    @property
    def history(self):
        return list(self._history)

    @property
    def last(self):
        return self._history[0] if self._history else None

    # -------------------------------------------------------------- persistence

    @property
    def _path(self):
        return os.path.join(self._data_folder, _HISTORY_FILE)

    def _load(self):
        try:
            with open(self._path, "r") as handle:
                data = json.load(handle)
        except IOError as exc:
            if exc.errno != errno.ENOENT:
                self._logger.warning("Could not read energy history: %s", exc)
            return
        except ValueError as exc:
            self._logger.warning("Energy history file is corrupt, ignoring it: %s", exc)
            return

        if isinstance(data, list):
            self._history = [entry for entry in data if isinstance(entry, dict)]
            del self._history[_HISTORY_LIMIT:]

    def _save(self):
        try:
            with open(self._path, "w") as handle:
                json.dump(self._history, handle)
        except (IOError, OSError) as exc:
            self._logger.warning("Could not write energy history: %s", exc)
