# coding=utf-8
"""Print-lifecycle automation.

Two small worker-thread controllers:

* :class:`AutoOffController` -- after a print ends, count down (cancellable),
  wait for the hotend to cool, then cut power.
* :class:`PowerOnController` -- power the printer up and reconnect to it.

Both use a :class:`threading.Event` rather than sleeping in a loop, so a cancel
takes effect immediately instead of at the end of the current tick.
"""

from __future__ import absolute_import, unicode_literals

import logging
import threading
import time

# Auto-off phases.
IDLE = "idle"
PENDING = "pending"      # cancellable grace period
COOLDOWN = "cooldown"    # waiting for the hotend to drop below the threshold
POWERING_OFF = "powering_off"
DONE = "done"
ABORTED = "aborted"

_COOLDOWN_POLL_INTERVAL = 5.0


class AutoOffController(object):
    """Runs the post-print power-off sequence."""

    def __init__(self, printer, power_off, notify, logger=None):
        """
        :param printer: OctoPrint printer interface (``self._printer``).
        :param power_off: callable taking an entity ID; raises on failure.
        :param notify: callable taking a dict, pushed to the UI.
        """
        self._printer = printer
        self._power_off = power_off
        self._notify = notify
        self._logger = logger or logging.getLogger(__name__)

        self._lock = threading.RLock()
        self._thread = None
        self._cancel = threading.Event()

        self._state = IDLE
        self._entity_id = None
        self._trigger = None
        self._seconds_remaining = 0
        self._detail = None

    # -------------------------------------------------------------------- state

    @property
    def state(self):
        return self._state

    @property
    def active(self):
        return self._state in (PENDING, COOLDOWN, POWERING_OFF)

    def snapshot(self):
        with self._lock:
            return {
                "state": self._state,
                "entity_id": self._entity_id,
                "trigger": self._trigger,
                "seconds_remaining": self._seconds_remaining,
                "detail": self._detail,
            }

    def _set(self, state=None, seconds_remaining=None, detail=None, push=True):
        with self._lock:
            if state is not None:
                self._state = state
            if seconds_remaining is not None:
                self._seconds_remaining = int(seconds_remaining)
            self._detail = detail
            payload = self.snapshot()
        if push:
            payload["type"] = "autooff"
            self._notify(payload)

    # ------------------------------------------------------------------ control

    def schedule(self, entity_id, trigger, config):
        """Start the power-off sequence for ``entity_id``."""
        with self._lock:
            if self.active:
                self._logger.debug("Auto-off already running, ignoring %s", trigger)
                return False
            self._cancel = threading.Event()
            self._entity_id = entity_id
            self._trigger = trigger
            self._thread = threading.Thread(
                target=self._run,
                args=(entity_id, dict(config), self._cancel),
                name="ha_power_autooff",
            )
            self._thread.daemon = True

        self._logger.info(
            "Scheduling power-off of %s after %s", entity_id, trigger
        )
        self._thread.start()
        return True

    def cancel(self, reason="cancelled"):
        """Abort a running sequence. Safe to call when nothing is running."""
        with self._lock:
            if not self.active:
                return False
            self._cancel.set()
        self._logger.info("Auto-off cancelled (%s)", reason)
        return True

    def shutdown(self):
        self.cancel("shutdown")
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)

    # ------------------------------------------------------------------- worker

    def _run(self, entity_id, config, cancel):
        try:
            if not self._grace_period(config, cancel):
                return
            if not self._cooldown(config, cancel):
                return
            self._power_down(entity_id, config)
        except Exception:
            self._logger.exception("Auto-off sequence failed")
            self._set(ABORTED, 0, "Power-off failed, see octoprint.log")

    def _aborted_by_printer(self):
        """True if a print restarted while we were waiting."""
        try:
            return self._printer.is_printing() or self._printer.is_paused()
        except Exception:
            return False

    def _grace_period(self, config, cancel):
        remaining = int(config.get("grace_period", 60) or 0)
        self._set(PENDING, remaining, None)
        while remaining > 0:
            if cancel.wait(1):
                self._set(ABORTED, 0, "Cancelled")
                return False
            if self._aborted_by_printer():
                self._set(ABORTED, 0, "A print started, leaving the power on")
                return False
            remaining -= 1
            self._set(PENDING, remaining, None)
        return True

    def _cooldown(self, config, cancel):
        threshold = float(config.get("cooldown_temp", 40) or 0)
        timeout = float(config.get("cooldown_timeout", 900) or 0)
        include_bed = bool(config.get("include_bed", False))

        if threshold <= 0:
            return True

        deadline = time.time() + timeout if timeout > 0 else None
        self._set(COOLDOWN, 0, "Waiting for the printer to cool below {:.0f}C".format(threshold))

        while True:
            hottest, label = self._hottest(include_bed)
            if hottest is None:
                # No temperature readings (printer already disconnected, or a
                # printer without a heater). Nothing to wait for.
                return True
            if hottest <= threshold:
                return True
            if deadline is not None and time.time() >= deadline:
                self._logger.info(
                    "Cooldown timeout reached with %s at %.1fC; powering off anyway",
                    label,
                    hottest,
                )
                self._set(COOLDOWN, 0, "Cooldown timed out, powering off")
                return True

            self._set(
                COOLDOWN,
                0,
                "Cooling: {} at {:.0f}C, waiting for {:.0f}C".format(
                    label, hottest, threshold
                ),
            )
            if cancel.wait(_COOLDOWN_POLL_INTERVAL):
                self._set(ABORTED, 0, "Cancelled")
                return False
            if self._aborted_by_printer():
                self._set(ABORTED, 0, "A print started, leaving the power on")
                return False

    def _hottest(self, include_bed):
        """Return ``(temperature, label)`` for the hottest tracked component."""
        try:
            temps = self._printer.get_current_temperatures() or {}
        except Exception:
            return None, None

        hottest = None
        label = None
        for key, values in temps.items():
            if key == "bed" and not include_bed:
                continue
            if key != "bed" and not key.startswith("tool"):
                continue
            actual = (values or {}).get("actual")
            if actual is None:
                continue
            if hottest is None or actual > hottest:
                hottest = actual
                label = "bed" if key == "bed" else key
        return hottest, label

    def _power_down(self, entity_id, config):
        self._set(POWERING_OFF, 0, "Turning off {}".format(entity_id))

        if config.get("disconnect_first", True):
            try:
                self._printer.disconnect()
                # Give the serial port a moment to close before the plug drops.
                time.sleep(1)
            except Exception:
                self._logger.exception("Could not disconnect from the printer")

        self._power_off(entity_id)
        self._set(DONE, 0, "Powered off {}".format(entity_id))


class PowerOnController(object):
    """Powers the printer plug on and optionally reconnects OctoPrint to it."""

    def __init__(self, printer, power_on, notify, logger=None):
        self._printer = printer
        self._power_on = power_on
        self._notify = notify
        self._logger = logger or logging.getLogger(__name__)
        self._thread = None
        self._lock = threading.Lock()

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    def power_on(self, entity_id, auto_connect=True, connect_timeout=30):
        with self._lock:
            if self.busy:
                return False
            self._thread = threading.Thread(
                target=self._run,
                args=(entity_id, bool(auto_connect), int(connect_timeout or 0)),
                name="ha_power_poweron",
            )
            self._thread.daemon = True
        self._thread.start()
        return True

    def _run(self, entity_id, auto_connect, connect_timeout):
        try:
            self._power_on(entity_id)
        except Exception as exc:
            self._logger.exception("Could not power on %s", entity_id)
            self._notify({"type": "poweron", "state": "failed", "error": str(exc)})
            return

        if not auto_connect:
            self._notify({"type": "poweron", "state": "done"})
            return

        self._notify({"type": "poweron", "state": "connecting"})
        deadline = time.time() + max(connect_timeout, 0)
        while time.time() < deadline:
            try:
                if not self._printer.is_closed_or_error():
                    self._notify({"type": "poweron", "state": "connected"})
                    return
                self._printer.connect()
            except Exception:
                self._logger.debug("Connect attempt failed, retrying", exc_info=True)
            time.sleep(2)

        state = "connected" if not self._safe_closed() else "timeout"
        self._notify({"type": "poweron", "state": state})

    def _safe_closed(self):
        try:
            return self._printer.is_closed_or_error()
        except Exception:
            return True
