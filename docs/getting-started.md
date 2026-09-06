# Getting started

Install the plugin, connect it to Home Assistant, and switch one configured entity before enabling printer automation.

## Prerequisites

- OctoPrint 1.5.0 or newer, as declared in the plugin listing. Check your version in OctoPrint's **About** dialog.
- Python compatible with your OctoPrint installation. The plugin declares Python `>=3.7,<4`; its CI tests Python 3.9 and 3.12.
- Administrator access to OctoPrint for entering credentials.
- A Home Assistant instance reachable from the computer running OctoPrint, with an entity you can already switch there.

Power and energy sensors are optional. A plug without them can still be switched.

## Install

Open **Settings → Plugin Manager → Get More… → …from URL** and enter:

```text
https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/v0.1.2.zip
```

Install, restart OctoPrint when prompted, and verify that **Home Assistant Power** appears in Settings. See [Installation](installation.md) for command-line and source installs.

## First run

1. In Home Assistant, open your profile's **Security** section and create a long-lived access token. Copy it when shown. Home Assistant documents this in its [authentication guide](https://www.home-assistant.io/docs/authentication/).
2. Open **Settings → Home Assistant Power** in OctoPrint. Enter your Home Assistant base URL, for example `https://homeassistant.local:8123`, without `/api` or a dashboard path. Paste the token and leave certificate verification enabled for a trusted certificate.
3. Press **Test connection**. A successful test displays `API running.`. These controls use the values currently in the dialog, so you can test before saving.
4. Press **Load entities from Home Assistant**, then **Add entity**. Select your actual entity ID, such as `switch.printer_plug`, and give it the label `Printer`. Keep **Navbar** selected.
5. Choose that ID as **Printer entity**. Leave post-print power-off disabled for this first check, then press **Save**.
6. Open the navbar dropdown and turn the plug on. Its state dot should update after the follow-up poll, scheduled about 1.5 seconds after the service call. If the physical device does not respond, check it in Home Assistant and see [Troubleshooting](troubleshooting.md).

For printer operators, these Settings and navbar controls are the complete setup path. No configuration-file editing is required.

## What just happened

OctoPrint saved the Home Assistant connection and entity mapping. The plugin sends switching requests from the OctoPrint server to Home Assistant and polls entity states every 30 seconds by default. Your browser receives the resulting status through OctoPrint.

## Next steps

- Read [Usage](usage.md) before enabling post-print power-off: a cooldown timeout cuts power even above the selected temperature.
- Attach sensors using [Energy tracking](energy.md).
- Review defaults and permissions in [Configuration](configuration.md).
- Use the [API](api.md) for integrations with the plugin.
