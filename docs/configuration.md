# Configuration

Use **Settings → Home Assistant Power** for normal setup. Persisted values live under `plugins.homeassistant_power` in OctoPrint's `config.yaml`.

## Precedence

Saved OctoPrint plugin settings override `get_settings_defaults()` in the source. The plugin defines no separate environment-variable or command-line configuration layer. **Test connection**, **Load entities from Home Assistant**, and **Detect** can use unsaved connection values from the dialog. Regular polling and switching use saved settings.

Saving closes the previous HTTP client and restarts polling immediately. If editing `config.yaml` manually, stop OctoPrint first so a later settings save does not overwrite the edit.

## Connection and selection

Option names below are relative to `plugins.homeassistant_power`. Examples are illustrative values from the plugin's defaults, placeholders, and tests; substitute your actual server and entity IDs.

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `base_url` | string | `""` | Base URL without `/api` or a dashboard path. Example: `https://homeassistant.local:8123`. Whitespace and trailing slashes are trimmed. |
| `access_token` | string | `""` | Home Assistant long-lived token. Example: the token copied from your profile; never commit the real value. |
| `verify_certificate` | boolean | `true` | Verify HTTPS certificates. Example: `true`. |
| `request_timeout` | integer | `5` | HTTP request timeout in seconds, available through saved configuration. Example: `10`. Zero falls back to 5. |
| `poll_interval` | integer | `30` | State poll interval in seconds. Example: `15`. Values below 5 are clamped to 5; zero falls back to 30. |
| `entities` | list of mappings | `[]` | Configured controls. Example: `[{entity_id: switch.printer_plug, label: Printer}]`. |
| `printer_entity` | string | `""` | Configured entity for printer automation and per-print energy. Example: `switch.printer_plug`. Empty disables the printer selection. |

## Entity rows

These options belong to each item in `entities`.

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `entity_id` | string | no row | Home Assistant ID. Example: `switch.printer_plug`. Blank IDs, IDs without a dot, and non-mapping rows are dropped. |
| `label` | string | entity ID | Navbar label. Example: `Printer`. Blank labels fall back to the ID. |
| `show_in_navbar` | boolean | `true` | Show the row in the dropdown. Example: `true`. Hiding it does not remove API access. |
| `confirm_off` | boolean | `false` | Ask in the browser before turning off an entity currently shown as on. Example: `true`. This is a UI preference, not an API permission. |
| `power_sensor` | string | empty / `null` | Instantaneous power sensor. Example: `sensor.printer_plug_power`. Blank values normalize to `null`. |
| `energy_sensor` | string | empty / `null` | Cumulative energy sensor. Example: `sensor.printer_plug_energy`. Blank values normalize to `null`. |

Discovery offers `switch`, `light`, `input_boolean`, `fan`, `siren`, and `humidifier` entities. Manually entered IDs use their domain's `turn_on` and `turn_off` services. `group` is mapped to the `homeassistant` service domain. An ID containing a dot passes normalization even if no corresponding entity or service exists; Home Assistant reports those failures when called.

## Power on

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `auto_on.enabled` | boolean | `false` | Reserved setting; no runtime path reads it. Example: `false`. It does not enable automatic power-on or gate the navbar button. |
| `auto_on.auto_connect` | boolean | `true` | Retry serial connection after the explicit power-on button. Example: `true`. |
| `auto_on.connect_timeout` | integer | `30` | Seconds to retry, at roughly two-second intervals. Example: `60`. Zero or negative values skip the retry loop. |

## Post-print power off

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `auto_off.enabled` | boolean | `false` | Enable post-print scheduling. Example: `true`. |
| `auto_off.on_done` | boolean | `true` | Schedule after `PrintDone`. Example: `true`. |
| `auto_off.on_failed` | boolean | `false` | Schedule after `PrintFailed`. Example: `false`. |
| `auto_off.on_cancelled` | boolean | `false` | Schedule after `PrintCancelled`. Example: `false`. |
| `auto_off.grace_period` | integer | `60` | Cancellable countdown in seconds. Example: `120`. Zero skips the wait. |
| `auto_off.cooldown_temp` | number | `40` | Maximum tracked actual temperature in °C before proceeding. Example: `40`. Zero or negative values skip cooldown. |
| `auto_off.include_bed` | boolean | `false` | Include the bed alongside every reported `tool*` heater. Example: `true`. |
| `auto_off.cooldown_timeout` | number | `900` | Maximum cooldown wait in seconds. Example: `0` to wait without a time limit while readings remain available. Zero or negative values mean no deadline. |
| `auto_off.disconnect_first` | boolean | `true` | Disconnect serial, then wait one second before switching off. Example: `true`. A disconnect exception is logged but does not stop power-off. |

!!! warning "Cooldown is not an unconditional temperature interlock"
    The plugin powers off when the cooldown timeout expires even if the printer is hot. It also proceeds if no tracked temperature readings are available. Setting the timeout to `0` removes the deadline, but does not change the missing-reading behavior. See [Usage](usage.md#post-print-power-off).

Use numeric values for numeric options and nonnegative values in the UI. The plugin has no comprehensive validation schema for manual edits. Invalid automation values can abort the worker and produce `Power-off failed, see octoprint.log`.

## Energy

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `energy.enabled` | boolean | `true` | Gate energy UI and starting per-print tracking. Example: `true`. Linked sensors remain part of state polling. |
| `energy.show_in_navbar` | boolean | `true` | Show live printer wattage in the navbar. Example: `true`. |
| `energy.show_sidebar` | boolean | `true` | Show the Printer Power sidebar while tracking or when a last-print record exists. Example: `true`. |
| `energy.track_per_print` | boolean | `true` | Start meter-difference tracking on print start. Example: `true`. |
| `energy.cost_per_kwh` | number | `0.0` | Rate used by the browser to estimate cost. Example: `0.15`. Nonpositive rates hide cost. |
| `energy.currency` | string | `"$"` | Display prefix; no currency conversion. Example: `CAD $`. |

## Examples

This configuration connects one printer plug and its sensors while leaving automatic shutdown disabled. Merge the block into your existing `plugins` mapping. Replace the token marker with your real token only in your private configuration.

```yaml title="config.yaml"
plugins:
  homeassistant_power:
    base_url: https://homeassistant.local:8123
    access_token: REPLACE_WITH_YOUR_LONG_LIVED_TOKEN
    verify_certificate: true
    request_timeout: 5
    poll_interval: 30
    entities:
      - entity_id: switch.printer_plug
        label: Printer
        show_in_navbar: true
        confirm_off: true
        power_sensor: sensor.printer_plug_power
        energy_sensor: sensor.printer_plug_energy
    printer_entity: switch.printer_plug
    auto_on:
      auto_connect: true
      connect_timeout: 30
    auto_off:
      enabled: false
      on_done: true
      on_failed: false
      on_cancelled: false
      grace_period: 60
      cooldown_temp: 40
      include_bed: false
      cooldown_timeout: 900
      disconnect_first: true
    energy:
      enabled: true
      show_in_navbar: true
      show_sidebar: true
      track_per_print: true
      cost_per_kwh: 0.15
      currency: "$"
```

## Permissions

| Operation | OctoPrint permission |
| --- | --- |
| Read the plugin's GET snapshot | `STATUS` |
| Switch plugs, power on, cancel auto-off, refresh, retrieve history | `PLUGIN_HOMEASSISTANT_POWER_CONTROL` |
| Test connection, list entities, detect sensors | `SETTINGS` |
| Read the stored access token back through settings | Administrator restriction |

**Control Home Assistant plugs** is granted to Admins and Users by default. Adjust group permissions in OctoPrint if a user should see status without switching plugs. All plugin API requests require authentication.
