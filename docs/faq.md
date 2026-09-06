# FAQ

These answers describe the current implementation. For a visible error, use [Troubleshooting](troubleshooting.md).

???+ question "Can I use a plug that has no energy sensor?"
    Yes. Leave the sensor fields empty. Switching and printer automation still work. A power sensor adds live watts; per-print totals require a cumulative energy sensor. The sidebar needs an active measurement or a previous record.

??? question "Will the printer power on automatically when I start a print?"
    No. Use **Power on printer & connect** before starting. OctoPrint cannot start a print while disconnected, and the plugin has no automatic power-on event handler. The saved `auto_on.enabled` value is unused.

??? question "Will power always stay on until the hotend is cool?"
    No. The default 900-second cooldown timeout cuts power even if the printer is still hot. Missing temperature readings also permit shutdown. Set `cooldown_timeout: 0` for no deadline while readings exist. Manual off commands bypass cooldown. See [Usage](usage.md#post-print-power-off).

??? question "Can I control lights or groups as well as switches?"
    Yes, if the entity supports on/off services. The service domain normally comes from the entity ID. Discovery lists switches, lights, input booleans, fans, sirens, and humidifiers. Enter groups manually; they use the generic `homeassistant` service domain.

??? question "Does energy include the cooldown after printing?"
    No. The final reading is taken when the print ends, before post-print power-off runs. Devices sharing the printer plug contribute to that meter during the measured interval.

??? question "Does restarting OctoPrint preserve the current print's measurement?"
    Completed history survives restart, up to 25 records. The current measurement does not. It exists only in memory until a print-end event completes it.

??? question "Why did the last print's cost change when I changed my electricity rate?"
    History stores kWh, not the rate or cost. The browser calculates the displayed estimate using your current rate. For example, 0.25 kWh at 0.15 per kWh gives 0.0375 before display rounding.

??? question "Does hiding a plug in the navbar prevent API switching?"
    No. `show_in_navbar` controls presentation. API switching is governed by the saved entity list and the plug-control permission. The row's **Confirm** setting is also a browser preference rather than an API access restriction.
