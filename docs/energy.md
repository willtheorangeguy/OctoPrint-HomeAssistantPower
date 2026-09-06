# Energy tracking

Use a power sensor for live watts and a cumulative energy sensor for per-print kilowatt-hours. The plugin does not integrate instantaneous watts over time.

## Attach sensors

In **Settings → Home Assistant Power**, press **Detect** beside an entity such as `switch.printer_plug`. The plugin first checks matching entity-ID stems, such as `sensor.printer_plug_power` and `sensor.printer_plug_energy`. It then tries friendly-name prefixes with matching `device_class` values. You can enter either sensor manually.

Detection is a naming heuristic, not a device-registry lookup. Confirm the sensors belong to the selected physical plug. Save the settings and wait for a poll.

## Accepted readings

| Reading | Accepted units | Stored/display base unit |
| --- | --- | --- |
| Power | `W`, `watt`, `kW`, `mW`, `milliwatt` | W |
| Energy | `Wh`, `kWh`, `MWh` | kWh |

Unit matching ignores case. Missing units default to W for power and kWh for energy. Unsupported units, nonnumeric values, `unknown`, and `unavailable` produce no reading.

For per-print tracking, the energy sensor's `state_class` must be `total_increasing`, `total`, or absent. `measurement` is rejected. Sensors without `state_class` are assumed to be cumulative, so choose them carefully.

## Per-print lifecycle

The plugin fetches a fresh reading directly from the selected printer's energy sensor on `PrintStarted`. It fetches another on `PrintDone`, `PrintFailed`, or `PrintCancelled` and subtracts the starting value. Current consumption between these events uses the polled reading.

```text
Start meter:   18.41 kWh
Finish meter:  18.66 kWh
Print energy:  0.25 kWh
```

The result is rounded to four decimal places. Missing start or finish readings prevent a record. If the finish reading is below the start, the plugin discards the measurement as a meter reset. It cannot detect a reset that later catches back up above the starting value.

This measures the selected plug during the print event interval. It excludes the later post-print cooldown wait. Other devices on that same plug contribute to the reading.

## History and cost

The plugin stores up to 25 completed records, newest first, in `energy_history.json` inside OctoPrint's plugin data folder for `homeassistant_power`. Each record contains `name`, `outcome`, `started`, `finished`, and `kwh`. Timestamps are Unix seconds. Outcomes are `done`, `failed`, or `cancelled`.

Completed history survives restart. The active measurement is held in memory and does not resume after restart. A corrupt history file is ignored with a warning in `octoprint.log`.

Cost is computed in the browser from kWh multiplied by the current `cost_per_kwh`. Rates and currency are not stored in history, so changing the rate changes the displayed estimate for the last print. A zero or negative rate hides cost.

Read the full history with the `energy_history` command described in [API](api.md#energy-history).
