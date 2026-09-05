# coding=utf-8

plugin_identifier = "homeassistant_power"
plugin_package = "octoprint_homeassistant_power"
plugin_name = "OctoPrint-HomeAssistantPower"
plugin_version = "0.1.0"
plugin_description = (
    "Control Home Assistant smart plugs from OctoPrint: switch them from the "
    "navbar, power the printer down after a print once it has cooled, and see "
    "how much energy each print used."
)
plugin_author = "William Vandergraaf"
plugin_author_email = "willtheorangeguy@outlook.com"
plugin_url = "https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower"
plugin_license = "AGPLv3"

# Nothing extra is needed at runtime: OctoPrint already ships `requests`.
plugin_requires = []

plugin_additional_data = []
plugin_additional_packages = []
plugin_ignored_packages = []

additional_setup_parameters = {
    "python_requires": ">=3.7,<4",
    "extras_require": {
        "develop": [
            "pytest>=7",
            "requests-mock>=1.10",
        ]
    },
}

# ----------------------------------------------------------------------------
# Below is the standard OctoPrint plugin setup boilerplate.

from setuptools import setup

try:
    import octoprint_setuptools
except Exception:
    print(
        "Could not import OctoPrint's setuptools, are you sure you are running "
        "that under the same python installation that OctoPrint is installed "
        "under?"
    )
    import sys

    sys.exit(-1)

setup_parameters = octoprint_setuptools.create_plugin_setup_parameters(
    identifier=plugin_identifier,
    package=plugin_package,
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    mail=plugin_author_email,
    url=plugin_url,
    license=plugin_license,
    requires=plugin_requires,
    additional_packages=plugin_additional_packages,
    ignored_packages=plugin_ignored_packages,
    additional_data=plugin_additional_data,
)

if len(additional_setup_parameters):
    from octoprint.util import dict_merge

    setup_parameters = dict_merge(setup_parameters, additional_setup_parameters)

setup(**setup_parameters)
