# Troubleshooting

Start with **Test connection** in Settings and the matching message in `octoprint.log`. Polling errors also appear in the plugin's status payload. Do not include your access token in a support request.

## Connection errors

| Message or symptom | Meaning | Action |
| --- | --- | --- |
| `Home Assistant is not configured yet` | The saved client lacks a base URL or token. | Enter both in Settings and save. Dialog tests can succeed with unsaved values while regular switching still uses the saved client. |
| `Home Assistant rejected the access token (401)` | Home Assistant rejected authentication. | Create a new long-lived token in Home Assistant and paste the complete value into Settings. |
| `The access token is not allowed to perform this action (403)` | Home Assistant refused the operation. | Check the Home Assistant account associated with the token and its access to the entity. |
| `Could not reach Home Assistant at ...` | The OctoPrint host could not connect. | Check hostname resolution, address, port, network routing, and Home Assistant availability from the OctoPrint host. |
| `Home Assistant did not respond within 5s` | The HTTP request timed out. | Check Home Assistant responsiveness and network connectivity. Adjust `request_timeout` if the service needs more time. |
| `TLS verification failed` | The HTTPS certificate could not be verified. | Use the hostname covered by a trusted certificate. For an intentionally self-signed installation, the plugin provides a certificate-verification checkbox. |
| `Home Assistant returned 404` | The requested API path was not found. | Check the entity ID and use the base URL without a dashboard path or `/api`. |
| `Home Assistant returned a non-JSON response` | The server returned something other than API JSON. | Check for a wrong URL or an intervening proxy/login page. |
| `does not look like a Home Assistant API endpoint` | The API greeting did not contain `API running`. | Check that the URL points at Home Assistant. |

For a connectivity check that sends no credentials, run this on the OctoPrint host and substitute your configured base URL:

```bash
curl -I https://homeassistant.local:8123/api/
```

An HTTP response, including an authentication error, shows that a server answered. This does not prove the plugin's credentials work; use **Test connection** for that.

## Switching failures

`switch.printer_plug is not one of the configured entities.` means the requested ID is not in the saved entity list. Add it and save before sending a switching command.

`A print is running on this printer.` means the server declined an unconfirmed printer power-off. Cancel the action, or explicitly confirm in the navbar if interrupting that print is intended. Manual switching does not wait for cooldown.

`No printer entity is configured in the settings.` means **Printer entity** is empty. Select one of the saved rows.

If controls are disabled or the plugin API returns HTTP 403, check OctoPrint permissions. `STATUS` allows GET snapshots; plug control needs **Control Home Assistant plugs**. This is distinct from a Home Assistant 403, which the plugin normally wraps in an HTTP 200 JSON response with `ok: false`.

## State is stale or unknown

Polling defaults to 30 seconds. A successful service call schedules an earlier poll after about 1.5 seconds; it does not set the cached state immediately. A Home Assistant request failure clears the state cache. An entity missing from the state list becomes `state: unknown, available: false`.

Home Assistant can return an entity whose literal state is `unavailable`. The API's `available` field only indicates that the entity exists in the returned list, so inspect `state` as well.

## Power-on connection timeout

The plug can turn on successfully while serial reconnection times out. Check the cable, configured port, and printer boot time. Increase **Connect timeout**, or connect manually through OctoPrint. The power-on worker uses OctoPrint's existing connection settings.

## Unexpected post-print power-off

Check **Trigger on**, **Cancel window**, **Cool down to**, and **Cooldown timeout**. The timeout deliberately proceeds with power-off even above the selected temperature. Missing temperature readings also allow it to proceed. Manual switching bypasses the cooldown entirely. See [Usage](usage.md#post-print-power-off).

`Power-off failed, see octoprint.log` means the automation worker caught an exception. Inspect the corresponding traceback and Home Assistant error. `Auto power-off is enabled but no printer entity is configured.` means the event could not schedule a shutdown.

## No watts or energy record

- Verify **Printer entity** and the sensor IDs. **Detect** may select the wrong similarly named sensor.
- Check the sensor's raw state and unit in Home Assistant. Unsupported units and nonnumeric values produce no reading.
- A power-only plug provides live watts but no per-print totals.
- Enable energy and per-print tracking before starting the print. A usable cumulative reading is needed at both start and finish.
- The sidebar appears only while tracking or when a last-print record exists. Live watts alone do not show it.

`Energy meter decreased during the print; discarding the reading.` indicates a reset or rollover. `Energy history file is corrupt, ignoring it` means persisted JSON could not be decoded. Back up the existing file before repairing or replacing it. See [Energy tracking](energy.md).

## Development install cannot import OctoPrint's setuptools

`Could not import OctoPrint's setuptools` comes from `setup.py` when `octoprint_setuptools` is unavailable. Install OctoPrint in the same active Python environment before the editable plugin install:

```bash
python -m pip install OctoPrint
python -m pip install -e ".[develop]"
```
