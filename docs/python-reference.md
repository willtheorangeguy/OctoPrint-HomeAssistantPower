# Python reference

These interfaces support the plugin's implementation. For integrations with a running OctoPrint server, use the [HTTP API](api.md). The reference below is generated from source with mkdocstrings rather than maintained as copied signatures.

## Sensor parsing

The unit-conversion example below is exercised by `test_energy.py`:

```python
from octoprint_homeassistant_power.energy import parse_power

reading = {"state": "1.5", "attributes": {"unit_of_measurement": "kW"}}
print(parse_power(reading))
```

```text
1500.0
```

::: octoprint_homeassistant_power.energy
    options:
      members:
        - parse_power
        - parse_energy
        - is_cumulative
        - detect_sensors
        - EnergyTracker

## Home Assistant transport

The client derives a service domain from an entity ID. For example, `group.everything` maps to `homeassistant`, as covered by the client tests.

::: octoprint_homeassistant_power.ha_client
    options:
      members:
        - domain_of
        - HomeAssistantError
        - HomeAssistantClient

## Automation controllers

OctoPrint creates these controllers at startup and supplies printer and notification callbacks. The [architecture guide](architecture.md) explains their boundaries, and [Usage](usage.md#post-print-power-off) documents the current shutdown behavior.

::: octoprint_homeassistant_power.automation
    options:
      members:
        - AutoOffController
        - PowerOnController
