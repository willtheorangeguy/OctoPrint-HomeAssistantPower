# coding=utf-8
"""Minimal Home Assistant REST API client.

Only depends on ``requests``, which OctoPrint already ships, so the plugin adds
no install dependencies.

Every failure is surfaced as a :class:`HomeAssistantError` carrying a message
that is safe (and useful) to show in the UI -- raw ``requests`` exceptions never
escape this module, and the access token is never included in a message or log
line.
"""

from __future__ import absolute_import, unicode_literals

import logging
import threading

import requests

# Entity domains that can be switched on and off, and are therefore offered as
# controllable entities in the settings dialog.
CONTROLLABLE_DOMAINS = (
    "switch",
    "light",
    "input_boolean",
    "fan",
    "siren",
    "humidifier",
)

# ``group`` entities are toggled through the generic ``homeassistant`` domain
# rather than through a domain of their own.
_DOMAIN_OVERRIDES = {"group": "homeassistant"}

_DEFAULT_TIMEOUT = 5


class HomeAssistantError(Exception):
    """Raised for any failure talking to Home Assistant."""

    def __init__(self, message, status_code=None):
        super(HomeAssistantError, self).__init__(message)
        self.message = message
        self.status_code = status_code


def domain_of(entity_id):
    """Return the service domain to use for ``entity_id``.

    ``switch.printer`` -> ``switch``, ``light.lamp`` -> ``light``,
    ``group.everything`` -> ``homeassistant``.

    Deriving the domain instead of assuming ``switch`` is what lets the plugin
    drive the same plug regardless of whether ZHA, Zigbee2MQTT or the IKEA
    DIRIGERA integration exposed it as a switch or as a light.
    """
    if not entity_id or "." not in entity_id:
        raise HomeAssistantError(
            "{!r} is not a valid entity ID (expected something like "
            "switch.my_plug)".format(entity_id)
        )
    domain = entity_id.split(".", 1)[0]
    return _DOMAIN_OVERRIDES.get(domain, domain)


class HomeAssistantClient(object):
    """Thread-safe wrapper around the Home Assistant REST API."""

    def __init__(
        self,
        base_url,
        access_token,
        verify_certificate=True,
        timeout=_DEFAULT_TIMEOUT,
        logger=None,
    ):
        self._base_url = (base_url or "").strip().rstrip("/")
        self._access_token = (access_token or "").strip()
        self._verify = bool(verify_certificate)
        self._timeout = timeout or _DEFAULT_TIMEOUT
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": "Bearer {}".format(self._access_token),
                "Content-Type": "application/json",
            }
        )

        if not self._verify:
            # The user has explicitly opted into an unverified connection (a
            # self-signed certificate on a LAN instance), so silence the
            # per-request warning rather than spamming the OctoPrint log.
            try:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:  # pragma: no cover - urllib3 is always present
                pass

    # ------------------------------------------------------------------ config

    @property
    def base_url(self):
        return self._base_url

    @property
    def configured(self):
        return bool(self._base_url and self._access_token)

    def matches(self, base_url, access_token, verify_certificate, timeout):
        """True if this client was built from exactly these settings."""
        return (
            self._base_url == (base_url or "").strip().rstrip("/")
            and self._access_token == (access_token or "").strip()
            and self._verify == bool(verify_certificate)
            and self._timeout == (timeout or _DEFAULT_TIMEOUT)
        )

    def close(self):
        try:
            self._session.close()
        except Exception:
            pass

    # ----------------------------------------------------------------- request

    def _request(self, method, path, payload=None):
        if not self.configured:
            raise HomeAssistantError(
                "Home Assistant is not configured yet - set the server URL and "
                "access token in the plugin settings."
            )

        url = "{}/api{}".format(self._base_url, path)
        try:
            with self._lock:
                response = self._session.request(
                    method,
                    url,
                    json=payload,
                    timeout=self._timeout,
                    verify=self._verify,
                )
        except requests.exceptions.SSLError:
            raise HomeAssistantError(
                "TLS verification failed. If Home Assistant uses a self-signed "
                "certificate, disable 'Verify certificate' in the settings."
            )
        except requests.exceptions.Timeout:
            raise HomeAssistantError(
                "Home Assistant did not respond within {}s.".format(self._timeout)
            )
        except requests.exceptions.ConnectionError:
            raise HomeAssistantError(
                "Could not reach Home Assistant at {}.".format(self._base_url)
            )
        except requests.exceptions.RequestException as exc:
            # Never let a raw requests exception out; its string form can embed
            # request details in some versions.
            raise HomeAssistantError(
                "Request to Home Assistant failed ({}).".format(type(exc).__name__)
            )

        if response.status_code == 401:
            raise HomeAssistantError(
                "Home Assistant rejected the access token (401). Create a new "
                "long-lived access token and paste it into the settings.",
                status_code=401,
            )
        if response.status_code == 403:
            raise HomeAssistantError(
                "The access token is not allowed to perform this action (403).",
                status_code=403,
            )
        if response.status_code == 404:
            raise HomeAssistantError(
                "Home Assistant returned 404 for {} - check the entity ID, and "
                "that the server URL has no trailing path.".format(path),
                status_code=404,
            )
        if response.status_code >= 400:
            raise HomeAssistantError(
                "Home Assistant returned HTTP {}.".format(response.status_code),
                status_code=response.status_code,
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise HomeAssistantError(
                "Home Assistant returned a non-JSON response - is {} really a "
                "Home Assistant instance?".format(self._base_url)
            )

    # --------------------------------------------------------------------- API

    def test_connection(self):
        """Return the greeting from ``GET /api/``, raising on any problem."""
        result = self._request("GET", "/")
        message = (result or {}).get("message", "")
        if "API running" not in message:
            raise HomeAssistantError(
                "Connected, but {} does not look like a Home Assistant API "
                "endpoint.".format(self._base_url)
            )
        return message

    def get_state(self, entity_id):
        """Return the full state object for a single entity."""
        return self._request("GET", "/states/{}".format(entity_id))

    def get_all_states(self):
        """Return every entity state, indexed by entity ID.

        The polling loop uses this single call rather than one request per
        entity: a handful of plugs each with power and energy sensors would
        otherwise mean a dozen requests per tick.
        """
        states = self._request("GET", "/states") or []
        return {
            entry["entity_id"]: entry
            for entry in states
            if isinstance(entry, dict) and entry.get("entity_id")
        }

    def call_service(self, entity_id, service):
        """Call ``<domain>.<service>`` for ``entity_id``."""
        domain = domain_of(entity_id)
        return self._request(
            "POST",
            "/services/{}/{}".format(domain, service),
            payload={"entity_id": entity_id},
        )

    def turn_on(self, entity_id):
        return self.call_service(entity_id, "turn_on")

    def turn_off(self, entity_id):
        return self.call_service(entity_id, "turn_off")

    def toggle(self, entity_id):
        return self.call_service(entity_id, "toggle")
