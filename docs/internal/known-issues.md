# Known issues

Concrete defects and gaps found while writing this repository's documentation.
**Nothing here was changed** — each one needs a code, configuration, or
licensing decision rather than a documentation one.

Ordered by severity. See [`docs/roadmap.md`](../roadmap.md) for the narrative version,
which also covers deliberate non-goals.

**3 open:** 3 high.

## Final power-off does not recheck cancellation or printer state

**Severity:** High

**Where:** `octoprint_homeassistant_power/automation.py`: `_run`, `_cooldown`, `_power_down`

**What:** Wait loops check cancellation and print state, but `_power_down` does not. Cooldown may return immediately for a cold printer, no readings, or an expired timeout. Cancellation or a new print after the final wait check cannot reliably stop the subsequent service call.

**Why it matters:** A printer can lose power despite a late cancellation or a newly started print. A zero cancel window makes the unchecked path easier to reach.

**Suggested fix:** Recheck cancellation and printing/paused state immediately before disconnect and before the off service, and add deterministic tests for cancellation at the worker phase boundaries.

## Manual printer power-off confirmation does not cover paused prints

**Severity:** High

**Where:** `octoprint_homeassistant_power/__init__.py`: `_command_turn_off`

**What:** The server guard checks only `_printer.is_printing()`. It does not check `is_paused()`. The optional row-level confirmation is a browser preference and defaults to false.

**Why it matters:** A paused print can be powered off through the API or default UI without the mid-print confirmation response, losing the ability to resume.

**Suggested fix:** Include paused jobs in the server guard and add API tests for printing, paused, idle, and explicitly forced requests.

## README overstates cooldown guarantees and narrows accepted energy sensors

**Severity:** High

**Where:** `README.md`: Features and Known limitations; `octoprint_homeassistant_power/automation.py`: `_cooldown`; `energy.py`: `is_cumulative`

**What:** The README says nothing is switched while the printer is still hot, but the worker powers off at timeout or with no readings. It also describes only total_increasing meters, while source and tests accept total and absent state_class too.

**Why it matters:** Readers can assume a temperature guarantee the plugin does not provide or reject a compatible meter. The MkDocs rollout explicitly preserves the root README, so the new guides document the source behavior and this discrepancy remains recorded.

**Suggested fix:** Revise the README feature claim to describe timeout and missing-reading behavior, and expand its energy requirements to match the tested state classes.
