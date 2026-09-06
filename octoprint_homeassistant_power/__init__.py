# coding=utf-8
"""Control Home Assistant smart plugs from OctoPrint."""

from __future__ import absolute_import, unicode_literals

import threading

import flask
import octoprint.plugin
from octoprint.access import ADMIN_GROUP, USER_GROUP
from octoprint.access.permissions import Permissions
from octoprint.events import Events
from octoprint.util import RepeatedTimer

from .automation import AutoOffController, PowerOnController
from .energy import (
    EnergyTracker,
    detect_sensors,
    is_cumulative,
    parse_energy,
    parse_power,
)
from .ha_client import CONTROLLABLE_DOMAINS, HomeAssistantClient, HomeAssistantError

__plugin_name__ = "Home Assistant Power"
__plugin_pythoncompat__ = ">=3.7,<4"

_MIN_POLL_INTERVAL = 5


class HomeAssistantPowerPlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
):
    def __init__(self):
        super(HomeAssistantPowerPlugin, self).__init__()
        self._client = None
        self._client_lock = threading.Lock()
        self._timer = None
        self._states = {}
        self._last_error = None
        self._auto_off = None
        self._power_on = None
        self._energy = None

    # ------------------------------------------------------------ SettingsPlugin

    def get_settings_defaults(self):
        return {
            "base_url": "",
            "access_token": "",
            "verify_certificate": True,
            "request_timeout": 5,
            "poll_interval": 30,
            # [{entity_id, label, show_in_navbar, confirm_off,
            #   power_sensor, energy_sensor}]
            "entities": [],
            "printer_entity": "",
            "energy": {
                "enabled": True,
                "show_in_navbar": True,
                "show_sidebar": True,
                "track_per_print": True,
                "cost_per_kwh": 0.0,
                "currency": "$",
            },
            "auto_on": {
                "enabled": False,
                "auto_connect": True,
                "connect_timeout": 30,
            },
            "auto_off": {
                "enabled": False,
                "on_done": True,
                "on_failed": False,
                "on_cancelled": False,
                "grace_period": 60,
                "cooldown_temp": 40,
                "include_bed": False,
                "cooldown_timeout": 900,
                "disconnect_first": True,
            },
        }

    def get_settings_restricted_paths(self):
        # Keep the long-lived access token out of every settings payload sent to
        # anyone who is not an admin.
        return {"admin": [["access_token"]]}

    def get_settings_version(self):
        return 1

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        # Rebuild the client against the new credentials and re-poll straight
        # away, so the UI reflects the change without waiting a full interval.
        with self._client_lock:
            if self._client is not None:
                self._client.close()
            self._client = None
        self._restart_timer()

    # ------------------------------------------------------------- AssetPlugin

    def get_assets(self):
        return {
            "js": ["js/homeassistant_power.js"],
            "css": ["css/homeassistant_power.css"],
        }

    # ---------------------------------------------------------- TemplatePlugin

    def is_template_autoescaped(self):
        # The templates emit no pre-rendered markup, so autoescaping is safe and
        # is what OctoPrint 1.13 will enforce globally anyway.
        return True

    def get_template_configs(self):
        return [
            # The navbar entry is a dropdown, so the wrapper <li> needs the
            # Bootstrap class for the toggle to work.
            {"type": "navbar", "custom_bindings": True, "classes": ["dropdown"]},
            {
                "type": "sidebar",
                "name": "Printer Power",
                "icon": "plug",
                "custom_bindings": True,
            },
            {
                "type": "settings",
                "name": "Home Assistant Power",
                "custom_bindings": True,
            },
        ]

    # ----------------------------------------------------------- StartupPlugin

    def on_after_startup(self):
        self._energy = EnergyTracker(self.get_plugin_data_folder(), self._logger)
        self._auto_off = AutoOffController(
            self._printer, self._turn_off_entity, self._push, self._logger
        )
        self._power_on = PowerOnController(
            self._printer, self._turn_on_entity, self._push, self._logger
        )
        self._restart_timer()

    def on_shutdown(self):
        self._stop_timer()
        if self._auto_off:
            self._auto_off.shutdown()
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    # ------------------------------------------------------------------ client

    @property
    def client(self):
        """The Home Assistant client, rebuilt whenever the settings change."""
        base_url = self._settings.get(["base_url"])
        token = self._settings.get(["access_token"])
        verify = self._settings.get_boolean(["verify_certificate"])
        timeout = self._settings.get_int(["request_timeout"]) or 5

        with self._client_lock:
            if self._client is None or not self._client.matches(
                base_url, token, verify, timeout
            ):
                if self._client is not None:
                    self._client.close()
                self._client = HomeAssistantClient(
                    base_url,
                    token,
                    verify_certificate=verify,
                    timeout=timeout,
                    logger=self._logger,
                )
            return self._client

    # ------------------------------------------------------------------- timer

    def _restart_timer(self):
        self._stop_timer()
        interval = max(
            self._settings.get_int(["poll_interval"]) or 30, _MIN_POLL_INTERVAL
        )
        self._timer = RepeatedTimer(interval, self._poll, run_first=True)
        self._timer.start()

    def _stop_timer(self):
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None

    def _poll(self):
        """Refresh every configured entity from a single /api/states call."""
        if not self.client.configured:
            return
        try:
            all_states = self.client.get_all_states()
        except HomeAssistantError as exc:
            if self._last_error != exc.message:
                self._logger.warning("Home Assistant poll failed: %s", exc.message)
            self._last_error = exc.message
            self._states = {}
            self._push_snapshot()
            return
        except Exception:
            self._logger.exception("Unexpected error polling Home Assistant")
            return

        self._last_error = None
        states = self._build_states(all_states)
        if states != self._states:
            self._states = states
            self._push_snapshot()

    def _push_snapshot(self):
        """Push the same shape the API GET returns, so the UI needs no follow-up."""
        payload = self._payload()
        payload["type"] = "states"
        self._push(payload)

    def _build_states(self, all_states):
        """Merge switch state with its linked power/energy sensor readings."""
        result = {}
        for entity in self._entities():
            entity_id = entity["entity_id"]
            state = all_states.get(entity_id)
            entry = {
                "state": (state or {}).get("state", "unknown"),
                "available": state is not None,
                "power_w": None,
                "energy_kwh": None,
                "cumulative": True,
            }

            power_sensor = entity.get("power_sensor")
            if power_sensor:
                entry["power_w"] = parse_power(all_states.get(power_sensor))

            energy_sensor = entity.get("energy_sensor")
            if energy_sensor:
                energy_state = all_states.get(energy_sensor)
                entry["energy_kwh"] = parse_energy(energy_state)
                entry["cumulative"] = is_cumulative(energy_state)

            result[entity_id] = entry
        return result

    def _push(self, payload):
        try:
            self._plugin_manager.send_plugin_message(self._identifier, payload)
        except Exception:
            self._logger.exception("Could not push a plugin message")

    # ---------------------------------------------------------------- entities

    def _entities(self):
        """Configured entities, normalised and with blanks dropped."""
        entities = self._settings.get(["entities"], merged=True) or []
        result = []
        for raw in entities:
            if not isinstance(raw, dict):
                continue
            entity_id = (raw.get("entity_id") or "").strip()
            if not entity_id or "." not in entity_id:
                continue
            result.append(
                {
                    "entity_id": entity_id,
                    "label": (raw.get("label") or "").strip() or entity_id,
                    "show_in_navbar": raw.get("show_in_navbar", True),
                    "confirm_off": raw.get("confirm_off", False),
                    "power_sensor": (raw.get("power_sensor") or "").strip() or None,
                    "energy_sensor": (raw.get("energy_sensor") or "").strip() or None,
                }
            )
        return result

    def _entity(self, entity_id):
        for entity in self._entities():
            if entity["entity_id"] == entity_id:
                return entity
        return None

    @property
    def _printer_entity(self):
        return (self._settings.get(["printer_entity"]) or "").strip()

    def _turn_on_entity(self, entity_id):
        self.client.turn_on(entity_id)
        self._refresh_soon()

    def _turn_off_entity(self, entity_id):
        self.client.turn_off(entity_id)
        self._refresh_soon()

    def _refresh_soon(self):
        """Re-poll shortly after a service call, once HA has settled."""
        timer = threading.Timer(1.5, self._poll)
        timer.daemon = True
        timer.start()

    # --------------------------------------------------------------------- API

    def is_api_protected(self):
        # Reject unauthenticated requests outright; individual commands then
        # check the specific permission they need.
        return True

    def get_api_commands(self):
        return {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
            "toggle": ["entity_id"],
            "power_on_printer": [],
            "cancel_auto_off": [],
            "refresh": [],
            "list_entities": [],
            "test_connection": ["base_url", "access_token", "verify_certificate"],
            "detect_sensors": ["entity_id"],
            "energy_history": [],
        }

    def on_api_get(self, request):
        if not Permissions.STATUS.can():
            return flask.abort(403)
        return flask.jsonify(self._payload())

    def on_api_command(self, command, data):
        admin_commands = ("list_entities", "test_connection", "detect_sensors")
        if command in admin_commands:
            if not Permissions.SETTINGS.can():
                return flask.abort(403)
        elif not Permissions.PLUGIN_HOMEASSISTANT_POWER_CONTROL.can():
            return flask.abort(403)

        handler = getattr(self, "_command_{}".format(command), None)
        if handler is None:
            return flask.abort(400, description="Unknown command")

        try:
            return handler(data)
        except HomeAssistantError as exc:
            self._logger.warning("Command %s failed: %s", command, exc.message)
            return flask.jsonify(ok=False, error=exc.message)
        except Exception as exc:
            self._logger.exception("Command %s raised", command)
            return flask.jsonify(ok=False, error="{}".format(exc))

    # -- command handlers

    def _command_refresh(self, data):
        self._poll()
        return flask.jsonify(self._payload())

    def _command_turn_on(self, data):
        entity_id = data["entity_id"]
        self._guard_known(entity_id)
        self._turn_on_entity(entity_id)
        return flask.jsonify(ok=True)

    def _command_turn_off(self, data):
        entity_id = data["entity_id"]
        self._guard_known(entity_id)
        # Refuse to cut power to the printer mid-print unless the UI has
        # confirmed it with the user.
        if (
            entity_id == self._printer_entity
            and not data.get("force", False)
            and self._printer.is_printing()
        ):
            return flask.jsonify(
                ok=False,
                needs_confirmation=True,
                error="A print is running on this printer.",
            )
        self._turn_off_entity(entity_id)
        return flask.jsonify(ok=True)

    def _command_toggle(self, data):
        entity_id = data["entity_id"]
        current = (self._states.get(entity_id) or {}).get("state")
        if current == "on":
            return self._command_turn_off(data)
        self._guard_known(entity_id)
        self._turn_on_entity(entity_id)
        return flask.jsonify(ok=True)

    def _command_power_on_printer(self, data):
        entity_id = self._printer_entity
        if not entity_id:
            return flask.jsonify(
                ok=False, error="No printer entity is configured in the settings."
            )
        auto_on = self._settings.get(["auto_on"], merged=True) or {}
        started = self._power_on.power_on(
            entity_id,
            auto_connect=auto_on.get("auto_connect", True),
            connect_timeout=auto_on.get("connect_timeout", 30),
        )
        return flask.jsonify(ok=started)

    def _command_cancel_auto_off(self, data):
        return flask.jsonify(ok=self._auto_off.cancel("user request"))

    def _command_list_entities(self, data):
        all_states = self.client.get_all_states()
        controllable = []
        sensors = []
        for entity_id, state in sorted(all_states.items()):
            domain = entity_id.split(".", 1)[0]
            attributes = state.get("attributes") or {}
            entry = {
                "entity_id": entity_id,
                "name": attributes.get("friendly_name", entity_id),
            }
            if domain in CONTROLLABLE_DOMAINS:
                controllable.append(entry)
            elif domain == "sensor":
                entry["unit"] = attributes.get("unit_of_measurement")
                entry["device_class"] = attributes.get("device_class")
                sensors.append(entry)
        return flask.jsonify(ok=True, controllable=controllable, sensors=sensors)

    def _command_test_connection(self, data):
        client = HomeAssistantClient(
            data.get("base_url"),
            data.get("access_token") or self._settings.get(["access_token"]),
            verify_certificate=data.get("verify_certificate", True),
            timeout=self._settings.get_int(["request_timeout"]) or 5,
            logger=self._logger,
        )
        try:
            message = client.test_connection()
        finally:
            client.close()
        return flask.jsonify(ok=True, message=message)

    def _command_detect_sensors(self, data):
        all_states = self.client.get_all_states()
        found = detect_sensors(data["entity_id"], all_states)
        return flask.jsonify(ok=True, **found)

    def _command_energy_history(self, data):
        return flask.jsonify(ok=True, history=self._energy.history)

    def _guard_known(self, entity_id):
        if self._entity(entity_id) is None:
            raise HomeAssistantError(
                "{} is not one of the configured entities.".format(entity_id)
            )

    def _payload(self):
        printer_entity = self._printer_entity
        printer_state = self._states.get(printer_entity) or {}
        energy_settings = self._settings.get(["energy"], merged=True) or {}
        return {
            "entities": self._entities(),
            "states": self._states,
            "printer_entity": printer_entity,
            "autooff": self._auto_off.snapshot() if self._auto_off else {},
            "error": self._last_error,
            "energy": {
                "settings": energy_settings,
                "current_kwh": self._energy.current_kwh(printer_state.get("energy_kwh"))
                if self._energy
                else None,
                "tracking": bool(self._energy and self._energy.tracking),
                "last": self._energy.last if self._energy else None,
            },
        }

    # ------------------------------------------------------- EventHandlerPlugin

    def on_event(self, event, payload):
        if event == Events.PRINT_STARTED:
            self._on_print_started(payload)
        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED):
            self._on_print_ended(event, payload)
        elif event in (Events.CONNECTED, Events.DISCONNECTED):
            self._refresh_soon()

    def _on_print_started(self, payload):
        # A new print supersedes any pending power-off.
        if self._auto_off:
            self._auto_off.cancel("a new print started")

        energy_settings = self._settings.get(["energy"], merged=True) or {}
        if not (
            energy_settings.get("enabled", True)
            and energy_settings.get("track_per_print", True)
        ):
            return

        state = self._printer_energy_state()
        if state is None:
            return
        self._energy.start_print(
            (payload or {}).get("name") or "print",
            state.get("energy_kwh"),
            cumulative=state.get("cumulative", True),
        )

    def _on_print_ended(self, event, payload):
        outcome = {
            Events.PRINT_DONE: "done",
            Events.PRINT_FAILED: "failed",
            Events.PRINT_CANCELLED: "cancelled",
        }[event]

        state = self._printer_energy_state()
        record = self._energy.finish_print(
            outcome, (state or {}).get("energy_kwh")
        ) if self._energy else None
        if record:
            self._push({"type": "print_energy", "record": record})

        self._maybe_schedule_auto_off(outcome)

    def _printer_energy_state(self):
        """Fresh reading for the printer plug, bypassing the poll cache."""
        entity = self._entity(self._printer_entity)
        if not entity or not entity.get("energy_sensor"):
            return None
        try:
            sensor_state = self.client.get_state(entity["energy_sensor"])
        except HomeAssistantError as exc:
            self._logger.warning("Could not read the energy sensor: %s", exc.message)
            return None
        return {
            "energy_kwh": parse_energy(sensor_state),
            "cumulative": is_cumulative(sensor_state),
        }

    def _maybe_schedule_auto_off(self, outcome):
        config = self._settings.get(["auto_off"], merged=True) or {}
        if not config.get("enabled", False):
            return

        wanted = {
            "done": config.get("on_done", True),
            "failed": config.get("on_failed", False),
            "cancelled": config.get("on_cancelled", False),
        }
        if not wanted.get(outcome, False):
            return

        entity_id = self._printer_entity
        if not entity_id:
            self._logger.warning(
                "Auto power-off is enabled but no printer entity is configured."
            )
            return

        self._auto_off.schedule(entity_id, outcome, config)

    # ------------------------------------------------------------------- hooks

    def get_additional_permissions(self, *args, **kwargs):
        return [
            {
                "key": "CONTROL",
                "name": "Control Home Assistant plugs",
                "description": "Allows switching the configured Home Assistant "
                "entities on and off from OctoPrint.",
                "roles": ["control"],
                "dangerous": False,
                "default_groups": [ADMIN_GROUP, USER_GROUP],
            }
        ]

    def get_update_information(self):
        return {
            "homeassistant_power": {
                "displayName": "Home Assistant Power",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "willtheorangeguy",
                "repo": "OctoPrint-HomeAssistantPower",
                "current": self._plugin_version,
                "pip": "https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/{target_version}.zip",
            }
        }


__plugin_implementation__ = HomeAssistantPowerPlugin()
__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions,
}
