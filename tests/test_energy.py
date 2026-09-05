# coding=utf-8
import pytest

from octoprint_homeassistant_power.energy import (
    EnergyTracker,
    detect_sensors,
    is_cumulative,
    parse_energy,
    parse_power,
)


def state(value, unit=None, **attributes):
    if unit is not None:
        attributes["unit_of_measurement"] = unit
    return {"state": value, "attributes": attributes}


class TestParsePower:
    @pytest.mark.parametrize(
        "value,unit,expected",
        [
            ("143.2", "W", 143.2),
            ("1.5", "kW", 1500.0),
            ("2500", "mW", 2.5),
            ("143.2", None, 143.2),  # default unit is W
        ],
    )
    def test_normalises_to_watts(self, value, unit, expected):
        assert parse_power(state(value, unit)) == pytest.approx(expected)

    @pytest.mark.parametrize("value", ["unavailable", "unknown", "", None, "n/a"])
    def test_missing_readings_are_none(self, value):
        assert parse_power(state(value, "W")) is None

    def test_unknown_unit_is_none_rather_than_a_guess(self):
        # Better no number than one that is off by a factor of 1000.
        assert parse_power(state("143", "A")) is None


class TestParseEnergy:
    @pytest.mark.parametrize(
        "value,unit,expected",
        [
            ("18.41", "kWh", 18.41),
            ("1840", "Wh", 1.84),
            ("0.5", "MWh", 500.0),
        ],
    )
    def test_normalises_to_kwh(self, value, unit, expected):
        assert parse_energy(state(value, unit)) == pytest.approx(expected)

    def test_unavailable_is_none(self):
        assert parse_energy(state("unavailable", "kWh")) is None


class TestIsCumulative:
    @pytest.mark.parametrize(
        "state_class,expected",
        [
            ("total_increasing", True),
            ("total", True),
            ("measurement", False),
            (None, True),  # sensors without a state_class are assumed to be meters
        ],
    )
    def test_state_class(self, state_class, expected):
        attributes = {} if state_class is None else {"state_class": state_class}
        assert is_cumulative({"state": "1", "attributes": attributes}) is expected


class TestDetectSensors:
    def test_matches_on_the_entity_id_stem(self):
        all_states = {
            "switch.printer_plug": state("on"),
            "sensor.printer_plug_power": state("140", "W"),
            "sensor.printer_plug_energy": state("18.4", "kWh"),
            "sensor.other_plug_power": state("5", "W"),
        }
        found = detect_sensors("switch.printer_plug", all_states)
        assert found["power_sensor"] == "sensor.printer_plug_power"
        assert found["energy_sensor"] == "sensor.printer_plug_energy"

    def test_falls_back_to_friendly_names(self):
        all_states = {
            "switch.plug_1": state("on", friendly_name="Printer Plug"),
            "sensor.zb_0x1234_power": state(
                "140", "W", friendly_name="Printer Plug Power", device_class="power"
            ),
            "sensor.zb_0x1234_energy": state(
                "18.4", "kWh", friendly_name="Printer Plug Energy", device_class="energy"
            ),
        }
        found = detect_sensors("switch.plug_1", all_states)
        assert found["power_sensor"] == "sensor.zb_0x1234_power"
        assert found["energy_sensor"] == "sensor.zb_0x1234_energy"

    def test_returns_nothing_when_the_plug_has_no_sensors(self):
        all_states = {"switch.dumb_plug": state("on")}
        assert detect_sensors("switch.dumb_plug", all_states) == {
            "power_sensor": None,
            "energy_sensor": None,
        }

    def test_handles_a_malformed_entity_id(self):
        assert detect_sensors("nonsense", {}) == {
            "power_sensor": None,
            "energy_sensor": None,
        }


class TestEnergyTracker:
    def test_records_the_delta_across_a_print(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("benchy.gcode", 18.400)
        assert tracker.current_kwh(18.550) == pytest.approx(0.15)
        record = tracker.finish_print("done", 18.820)
        assert record["kwh"] == pytest.approx(0.42)
        assert record["name"] == "benchy.gcode"
        assert record["outcome"] == "done"

    def test_meter_reset_is_discarded(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("benchy.gcode", 18.400)
        # The integration reloaded and the meter went back to zero.
        assert tracker.finish_print("done", 0.02) is None
        assert tracker.history == []

    def test_non_cumulative_sensors_are_not_tracked(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("benchy.gcode", 140.0, cumulative=False)
        assert tracker.tracking is False
        assert tracker.finish_print("done", 150.0) is None

    def test_missing_reading_at_start_is_not_tracked(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("benchy.gcode", None)
        assert tracker.tracking is False

    def test_history_survives_a_restart(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("a.gcode", 1.0)
        tracker.finish_print("done", 1.5)

        reloaded = EnergyTracker(str(tmp_path))
        assert len(reloaded.history) == 1
        assert reloaded.last["kwh"] == pytest.approx(0.5)

    def test_corrupt_history_file_is_ignored(self, tmp_path):
        (tmp_path / "energy_history.json").write_text("{not json")
        assert EnergyTracker(str(tmp_path)).history == []

    def test_abandon_drops_the_measurement(self, tmp_path):
        tracker = EnergyTracker(str(tmp_path))
        tracker.start_print("a.gcode", 1.0)
        tracker.abandon()
        assert tracker.finish_print("done", 2.0) is None
