# OctoPrint-HomeAssistantPower

Control your Home Assistant smart plugs from inside OctoPrint. Add Home Assistant entities to a navbar dropdown, run a cancellable power-off sequence after a print, and measure each print's electricity use when your plug provides an energy meter.

## Key features

- Switch multiple configured entities from the navbar, with labels and state indicators.
- Power on the printer and retry its serial connection from one button.
- Choose which print outcomes trigger a countdown and temperature wait before power-off.
- Display live watts for each plug and per-print kilowatt-hours for the selected printer.
- Estimate print cost from your configured electricity rate.
- Separate plug control permissions from status access and restrict token readback to administrators.

## Quick start

In OctoPrint's **Settings → Plugin Manager → Get More… → …from URL**, install this release archive, then restart OctoPrint:

```text
https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/v0.1.2.zip
```

Open **Settings → Home Assistant Power**, enter the server URL and a long-lived access token, and press **Test connection**. Add an entity such as `switch.printer_plug`, choose it as **Printer entity**, and save. Follow [Getting started](getting-started.md) for the complete setup and first switching check.

## Where to next

<div class="grid cards" markdown>

- **Set up your printer**

    [Installation](installation.md) and [configuration](configuration.md) cover prerequisites, credentials, and every setting.

- **Use the controls**

    [Usage](usage.md) explains switching, cancellation, and the cooldown timeout. [Energy tracking](energy.md) covers sensors and cost.

- **Resolve a problem**

    Match an error in [troubleshooting](troubleshooting.md), or read the [FAQ](faq.md) for behavior that may surprise you.

- **Work on the plugin**

    Start with [architecture](architecture.md), then [development](development.md), [testing](testing.md), and the [API](api.md).

</div>

## Support

File an [issue](https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/issues/new/choose). Include your plugin and OctoPrint versions, the relevant settings, and the error from `octoprint.log`. Remove access tokens before sharing logs or configuration.
