# Testing

The existing pytest suite covers the HTTP client, power-off controller, sensor parsing, and energy history. It uses mocked HTTP and fake printer objects, so it does not need a running Home Assistant server or printer.

## Run the suite

After the [development setup](development.md), run in the activated environment:

```bash
python -m pytest
```

`pytest.ini` sets `testpaths = tests`. Run a focused file when modifying a component:

```bash
python -m pytest tests/test_ha_client.py
python -m pytest tests/test_automation.py
python -m pytest tests/test_energy.py
```

## Coverage by component

| File | Behaviors exercised |
| --- | --- |
| `test_ha_client.py` | Domain selection, bearer authentication, service requests, error mapping, token omission from errors, configuration matching, state indexing, API greeting. |
| `test_automation.py` | Grace period, cooldown, bed inclusion, timeout proceeding with shutdown, cancellation, new-print abort, notifications, missing temperatures, power-off failure. |
| `test_energy.py` | Units, invalid readings, cumulative classification, sensor detection, meter differences, reset rejection, persistence, corrupt history, abandoning an active measurement. |

The suite does not provide browser tests, end-to-end Simple API permission tests, or direct `PowerOnController` tests. A passing suite does not prove real serial reconnection or physical cutoff timing.

## Manual integration checks

Use OctoPrint's Virtual Printer and a dedicated Home Assistant test entity for the first pass:

1. Test, discover, and save connection settings. Reopen Settings and confirm the selected printer remains selected.
2. Switch the test entity and confirm the navbar updates after a poll.
3. Finish a virtual print with auto-off enabled and cancel during the grace period.
4. Exercise a controlled cooldown and inspect phase notifications. Verify the documented timeout and missing-reading behavior against a test entity.
5. Check a user with status permission but no plug-control permission.
6. Use a cumulative meter to produce a completed record, restart OctoPrint, and confirm history survives.

## Documentation checks

After staging shared assets with the [preview helper](development.md#preview-documentation):

```bash
python -m mkdocs build --strict
npx --yes markdownlint-cli2 --config .mkdocs-shared/shared/lint/.markdownlint.jsonc "docs/**/*.md"
```

The strict build checks rendered links, anchors, includes, and configuration. The Markdown linter checks the shared writing rules. Documentation CI also runs an external link check; see [CI/CD](ci-cd.md).
