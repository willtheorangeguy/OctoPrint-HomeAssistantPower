---
layout: plugin

id: homeassistant_power
title: Home Assistant Power
description: Switch Home Assistant smart plugs from the OctoPrint navbar, cut printer power after a print once it has cooled down, and track energy use per print.
authors:
- William Vandergraaf
license: AGPLv3

date: 2026-09-05

homepage: https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower
source: https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower
archive: https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/v0.1.2.zip

tags:
- power
- home assistant
- smart plug
- automation
- energy
- psu

screenshots:
- url: /assets/img/plugins/homeassistant_power/navbar.png
  alt: The navbar showing live wattage, with a dropdown listing three smart plugs
  caption: The printer's live draw sits in the navbar; the dropdown controls every plug.
- url: /assets/img/plugins/homeassistant_power/autooff.png
  alt: A countdown notification offering to keep the power on
  caption: A cancellable countdown runs before the printer is powered off.
- url: /assets/img/plugins/homeassistant_power/settings.png
  alt: The plugin settings dialog showing the entity table and automation options
  caption: Entities, automation and energy options all live in one settings pane.

featuredimage: /assets/img/plugins/homeassistant_power/navbar.png

compatibility:
  octoprint:
  - 1.5.0

  os:
  - linux
  - windows
  - macos
  - freebsd

  python: ">=3.7,<4"

attributes:
- ai-developed

---

Control your Home Assistant smart plugs without leaving OctoPrint.

**Multi-plug navbar control.** Add any number of Home Assistant entities and get
a navbar dropdown with a state dot, live wattage and on/off buttons for each
one. Printer, enclosure light, filament dryer — whatever is on a plug.

**Power off after a print, safely.** When a print finishes, a cancellable
countdown appears. If you do not cancel it, the plugin waits for the hotend (and
optionally the bed) to cool below a temperature you choose, disconnects from the
printer, and only then cuts power — so the printer is never left hot with its
fans dead. The sequence aborts by itself if a new print starts.

**Power on and connect.** One button switches the printer plug on and retries
the serial connection until the printer has finished booting.

**Energy and cost.** If your plugs report power and energy, a sidebar panel
shows what the current print has used so far, what the last one used, and
optionally what it cost.

**Works with any plug integration.** The Home Assistant service domain is taken
from the entity ID, so `switch.*`, `light.*` and `input_boolean.*` entities all
work — which matters for Zigbee plugs, since ZHA, Zigbee2MQTT and vendor
integrations expose the same hardware in different domains.

**Safe by default.** Cutting power to the printer mid-print requires an explicit
confirmation, plug control is a separate OctoPrint permission you can revoke per
group, and the long-lived access token is only ever readable by administrators.

### Requirements

A reachable Home Assistant instance and a long-lived access token from your
Home Assistant profile page. The plugin installs no extra Python packages.

### Note on AI assistance

This plugin was written with AI assistance and is marked `ai-developed`
accordingly. It is maintained by a human who reads and understands the code.
