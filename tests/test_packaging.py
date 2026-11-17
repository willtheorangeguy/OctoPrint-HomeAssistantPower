"""Check the installed distribution OctoPrint uses to discover this plugin."""

import json
import sysconfig
from importlib.metadata import Distribution

import octoprint.plugin
from octoprint.plugin.core import PluginManager
import pytest


@pytest.fixture
def installed_distribution():
    # Ignore source-tree egg-info: only inspect metadata installed into this
    # interpreter's site-packages, including when pytest runs from the checkout.
    return next(Distribution.discover(
        name="OctoPrint-HomeAssistantPower",
        path=[sysconfig.get_path("purelib")],
    ))


def test_installed_plugin_entry_point(installed_distribution):
    dist = installed_distribution
    entry_point = next(
        ep for ep in dist.entry_points
        if ep.group == "octoprint.plugin" and ep.name == "homeassistant_power"
    )
    module = entry_point.load()
    plugin = module.__plugin_implementation__
    assert isinstance(plugin, octoprint.plugin.SettingsPlugin)
    assert isinstance(plugin, octoprint.plugin.SimpleApiPlugin)
    assert plugin.is_api_protected()
    assert plugin.is_template_autoescaped()
    assert "octoprint.access.permissions" in module.__plugin_hooks__


def test_octoprint_discovers_and_enables_plugin():
    manager = PluginManager(
        [], [octoprint.plugin.OctoPrintPlugin], ["octoprint.plugin"]
    )
    manager.reload_plugins(startup=True, initialize_implementations=False)
    info = manager.get_plugin_info("homeassistant_power")
    assert info is not None
    assert info.loaded
    assert info.enabled
    assert not info.incompatible


def test_wheel_contains_frontend_assets(installed_distribution):
    dist = installed_distribution
    source = json.loads(dist.read_text("direct_url.json") or "{}")
    if source.get("dir_info", {}).get("editable"):
        pytest.skip("Build and install the wheel to check packaged frontend assets")
    installed = {str(path).replace("\\", "/") for path in dist.files}
    for asset in (
        "templates/homeassistant_power_navbar.jinja2",
        "templates/homeassistant_power_settings.jinja2",
        "templates/homeassistant_power_sidebar.jinja2",
        "static/js/homeassistant_power.js",
        "static/css/homeassistant_power.css",
    ):
        path = "octoprint_homeassistant_power/" + asset
        assert path in installed, "Build and install the wheel before running packaging tests"
        assert dist.locate_file(path).is_file()
