# coding=utf-8
import pytest

from octoprint_homeassistant_power.ha_client import (
    HomeAssistantClient,
    HomeAssistantError,
    domain_of,
)

BASE = "https://ha.example"
TOKEN = "s3cret-token"


@pytest.fixture
def client():
    return HomeAssistantClient(BASE, TOKEN, timeout=1)


class TestDomainOf:
    @pytest.mark.parametrize(
        "entity_id,expected",
        [
            ("switch.printer_plug", "switch"),
            ("light.desk_lamp", "light"),
            ("input_boolean.holiday", "input_boolean"),
            # Groups are toggled through the generic domain.
            ("group.workshop", "homeassistant"),
        ],
    )
    def test_derives_domain(self, entity_id, expected):
        assert domain_of(entity_id) == expected

    @pytest.mark.parametrize("bad", ["", None, "switch", "no-dot-here"])
    def test_rejects_malformed(self, bad):
        with pytest.raises(HomeAssistantError):
            domain_of(bad)


class TestServiceCalls:
    def test_turn_on_uses_entity_domain(self, client, requests_mock):
        mock = requests_mock.post(BASE + "/api/services/light/turn_on", json=[])
        client.turn_on("light.desk_lamp")
        assert mock.called
        assert mock.last_request.json() == {"entity_id": "light.desk_lamp"}

    def test_turn_off_uses_entity_domain(self, client, requests_mock):
        mock = requests_mock.post(BASE + "/api/services/switch/turn_off", json=[])
        client.turn_off("switch.printer_plug")
        assert mock.called

    def test_sends_bearer_token(self, client, requests_mock):
        mock = requests_mock.post(BASE + "/api/services/switch/toggle", json=[])
        client.toggle("switch.printer_plug")
        assert mock.last_request.headers["Authorization"] == "Bearer " + TOKEN


class TestErrorMapping:
    def test_401_explains_the_token(self, client, requests_mock):
        requests_mock.get(BASE + "/api/states/switch.x", status_code=401)
        with pytest.raises(HomeAssistantError) as excinfo:
            client.get_state("switch.x")
        assert excinfo.value.status_code == 401
        assert "token" in excinfo.value.message.lower()

    def test_404_mentions_the_entity(self, client, requests_mock):
        requests_mock.get(BASE + "/api/states/switch.missing", status_code=404)
        with pytest.raises(HomeAssistantError) as excinfo:
            client.get_state("switch.missing")
        assert excinfo.value.status_code == 404
        assert "entity ID" in excinfo.value.message

    def test_timeout_becomes_a_friendly_error(self, client, requests_mock):
        import requests

        requests_mock.get(BASE + "/api/", exc=requests.exceptions.ConnectTimeout)
        with pytest.raises(HomeAssistantError) as excinfo:
            client.test_connection()
        assert "did not respond" in excinfo.value.message

    def test_connection_error_becomes_a_friendly_error(self, client, requests_mock):
        import requests

        requests_mock.get(BASE + "/api/", exc=requests.exceptions.ConnectionError)
        with pytest.raises(HomeAssistantError) as excinfo:
            client.test_connection()
        assert "Could not reach" in excinfo.value.message

    def test_non_json_response_is_reported(self, client, requests_mock):
        requests_mock.get(BASE + "/api/", text="<html>not home assistant</html>")
        with pytest.raises(HomeAssistantError) as excinfo:
            client.test_connection()
        assert "non-JSON" in excinfo.value.message

    def test_error_messages_never_contain_the_token(self, client, requests_mock):
        requests_mock.get(BASE + "/api/states/switch.x", status_code=500)
        with pytest.raises(HomeAssistantError) as excinfo:
            client.get_state("switch.x")
        assert TOKEN not in excinfo.value.message

    def test_unconfigured_client_refuses_to_call(self):
        with pytest.raises(HomeAssistantError):
            HomeAssistantClient("", "").get_state("switch.x")


class TestStates:
    def test_get_all_states_indexes_by_entity_id(self, client, requests_mock):
        requests_mock.get(
            BASE + "/api/states",
            json=[
                {"entity_id": "switch.a", "state": "on"},
                {"entity_id": "sensor.b", "state": "12.5"},
                {"not_an_entity": True},
            ],
        )
        states = client.get_all_states()
        assert set(states) == {"switch.a", "sensor.b"}
        assert states["switch.a"]["state"] == "on"

    def test_test_connection_rejects_a_non_ha_endpoint(self, client, requests_mock):
        requests_mock.get(BASE + "/api/", json={"message": "hello"})
        with pytest.raises(HomeAssistantError):
            client.test_connection()

    def test_test_connection_accepts_home_assistant(self, client, requests_mock):
        requests_mock.get(BASE + "/api/", json={"message": "API running."})
        assert "API running" in client.test_connection()


def test_matches_detects_settings_changes(client):
    assert client.matches(BASE, TOKEN, True, 1)
    assert not client.matches(BASE, "other-token", True, 1)
    assert not client.matches("https://elsewhere", TOKEN, True, 1)
    assert not client.matches(BASE, TOKEN, False, 1)


def test_trailing_slash_is_stripped():
    assert HomeAssistantClient(BASE + "/", TOKEN).base_url == BASE
