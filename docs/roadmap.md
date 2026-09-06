# Roadmap

The repository identifies polling and cumulative-meter requirements as current limitations. It does not define a release schedule for changing them.

## State updates

Home Assistant state is polled every 30 seconds by default, with a five-second minimum. The README identifies WebSocket updates as a possible next step. No WebSocket client is implemented.

## Energy measurement

A cumulative energy sensor is required for per-print totals. For example, a plug reporting only `143.2 W` can show live draw but cannot produce a print's kWh total. The plugin does not integrate power over time or retain a full long-term history: it stores at most 25 completed records.

## Printer automation

One configured entity represents the printer for automation and per-print energy. Power-on is a manual button action with optional serial retries. There is no automatic power-on-before-printing hook.

The current power-off behavior has specific timeout and cancellation limits documented in [Usage](usage.md#post-print-power-off). Defects found during the documentation pass are tracked separately in the repository's `docs/internal/known-issues.md`, outside the published site.

## Proposing work

Use [GitHub issues](https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/issues) to propose a change with a concrete use case. Check [Architecture](architecture.md) and [Testing](testing.md) before implementing changes to event handling or measurement.
