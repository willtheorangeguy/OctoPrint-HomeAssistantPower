# coding=utf-8
"""Tests for the post-print power-off sequence.

The controller runs on a worker thread, so these tests use very short grace
periods and poll for the terminal state rather than sleeping a fixed amount.
"""

import threading
import time

import pytest

from octoprint_homeassistant_power import automation
from octoprint_homeassistant_power.automation import AutoOffController


class FakePrinter:
    def __init__(self, temps=None, printing=False):
        self.temps = temps if temps is not None else {"tool0": {"actual": 25.0}}
        self.printing = printing
        self.paused = False
        self.disconnected = False

    def get_current_temperatures(self):
        return self.temps

    def is_printing(self):
        return self.printing

    def is_paused(self):
        return self.paused

    def disconnect(self):
        self.disconnected = True


class Recorder:
    def __init__(self):
        self.messages = []
        self.powered_off = []
        self.lock = threading.Lock()

    def notify(self, payload):
        with self.lock:
            self.messages.append(payload)

    def power_off(self, entity_id):
        with self.lock:
            self.powered_off.append(entity_id)

    def states(self):
        with self.lock:
            return [message["state"] for message in self.messages]


def config(**overrides):
    base = {
        "grace_period": 1,
        "cooldown_temp": 40,
        "include_bed": False,
        "cooldown_timeout": 10,
        "disconnect_first": True,
    }
    base.update(overrides)
    return base


def wait_for(predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(autouse=True)
def fast_cooldown_polling(monkeypatch):
    # Keep the cooldown loop responsive so tests stay quick.
    monkeypatch.setattr(automation, "_COOLDOWN_POLL_INTERVAL", 0.05)


def build(printer, recorder):
    return AutoOffController(printer, recorder.power_off, recorder.notify)


class TestHappyPath:
    def test_cold_printer_powers_off(self):
        printer = FakePrinter(temps={"tool0": {"actual": 25.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=0))

        assert wait_for(lambda: controller.state == automation.DONE)
        assert recorder.powered_off == ["switch.printer"]
        assert printer.disconnected is True

    def test_waits_for_the_hotend_to_cool(self):
        printer = FakePrinter(temps={"tool0": {"actual": 210.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=0))

        assert wait_for(lambda: controller.state == automation.COOLDOWN)
        assert recorder.powered_off == []

        printer.temps = {"tool0": {"actual": 35.0}}
        assert wait_for(lambda: controller.state == automation.DONE)
        assert recorder.powered_off == ["switch.printer"]

    def test_hot_bed_is_ignored_unless_requested(self):
        printer = FakePrinter(temps={"tool0": {"actual": 25.0}, "bed": {"actual": 60.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=0))

        assert wait_for(lambda: controller.state == automation.DONE)

    def test_bed_is_honoured_when_requested(self):
        printer = FakePrinter(temps={"tool0": {"actual": 25.0}, "bed": {"actual": 60.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule(
            "switch.printer", "done", config(grace_period=0, include_bed=True)
        )

        assert wait_for(lambda: controller.state == automation.COOLDOWN)
        assert recorder.powered_off == []
        controller.cancel("test teardown")

    def test_cooldown_timeout_powers_off_anyway(self):
        printer = FakePrinter(temps={"tool0": {"actual": 210.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule(
            "switch.printer", "done", config(grace_period=0, cooldown_timeout=0.2)
        )

        assert wait_for(lambda: controller.state == automation.DONE)
        assert recorder.powered_off == ["switch.printer"]

    def test_disconnect_can_be_skipped(self):
        printer = FakePrinter()
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule(
            "switch.printer", "done", config(grace_period=0, disconnect_first=False)
        )

        assert wait_for(lambda: controller.state == automation.DONE)
        assert printer.disconnected is False


class TestCancellation:
    def test_cancel_during_the_grace_period(self):
        printer = FakePrinter()
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=30))
        assert wait_for(lambda: controller.state == automation.PENDING)

        assert controller.cancel("test") is True
        assert wait_for(lambda: controller.state == automation.ABORTED)
        assert recorder.powered_off == []

    def test_cancel_during_cooldown(self):
        printer = FakePrinter(temps={"tool0": {"actual": 210.0}})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=0))
        assert wait_for(lambda: controller.state == automation.COOLDOWN)

        controller.cancel("test")
        assert wait_for(lambda: controller.state == automation.ABORTED)
        assert recorder.powered_off == []

    def test_cancel_when_idle_is_a_no_op(self):
        controller = build(FakePrinter(), Recorder())
        assert controller.cancel("test") is False

    def test_a_new_print_aborts_the_sequence(self):
        printer = FakePrinter()
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=30))
        assert wait_for(lambda: controller.state == automation.PENDING)

        printer.printing = True
        assert wait_for(lambda: controller.state == automation.ABORTED)
        assert recorder.powered_off == []

    def test_second_schedule_is_ignored_while_running(self):
        controller = build(FakePrinter(), Recorder())
        assert controller.schedule("switch.printer", "done", config(grace_period=30))
        assert not controller.schedule("switch.printer", "done", config(grace_period=30))
        controller.cancel("test teardown")


class TestReporting:
    def test_countdown_is_pushed_every_second(self):
        recorder = Recorder()
        controller = build(FakePrinter(), recorder)

        controller.schedule("switch.printer", "done", config(grace_period=2))
        assert wait_for(lambda: controller.state == automation.DONE)

        countdowns = [
            message["seconds_remaining"]
            for message in recorder.messages
            if message.get("state") == automation.PENDING
        ]
        assert countdowns[0] == 2
        assert countdowns[-1] == 0

    def test_missing_temperatures_do_not_block_power_off(self):
        printer = FakePrinter(temps={})
        recorder = Recorder()
        controller = build(printer, recorder)

        controller.schedule("switch.printer", "done", config(grace_period=0))

        assert wait_for(lambda: controller.state == automation.DONE)

    def test_power_off_failure_is_reported_not_raised(self):
        def explode(entity_id):
            raise RuntimeError("Home Assistant unreachable")

        recorder = Recorder()
        controller = AutoOffController(FakePrinter(), explode, recorder.notify)
        controller.schedule("switch.printer", "done", config(grace_period=0))

        assert wait_for(lambda: controller.state == automation.ABORTED)
