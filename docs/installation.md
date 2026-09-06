# Installation

<!-- markdownlint-disable MD046 -->
<!-- Material content tabs require indentation around fenced code blocks. -->

Install into the same Python environment that runs OctoPrint. The plugin's package is `OctoPrint-HomeAssistantPower`, and its import package is `octoprint_homeassistant_power`.

## Requirements

| Component | Requirement |
| --- | --- |
| OctoPrint | The plugin listing declares `>=1.5.0`. |
| Python | Plugin metadata declares `>=3.7,<4`; the installed OctoPrint release may require a newer Python. CI covers 3.9 and 3.12. |
| Home Assistant | A reachable REST API and a long-lived access token. The repository declares no minimum Home Assistant version. |
| Network | OctoPrint must reach the Home Assistant base URL. Browser-only reachability is insufficient. |
| Dependencies | No additional runtime packages are declared. The plugin uses `requests` supplied by OctoPrint. |
| Operating system | Use an environment supported by your OctoPrint installation. The plugin declares no separate OS restriction. |

Keep the OctoPrint host powered independently if the printer plug also supplies accessories. The plugin disconnects the printer's serial connection; it does not shut down the host operating system.

## Install methods

=== "Plugin Manager"

    Open **Settings → Plugin Manager → Get More… → …from URL** and install:

    ```text
    https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/v0.1.2.zip
    ```

    Restart OctoPrint when prompted. This is the recommended path for an existing installation.

=== "Release archive with pip"

    Activate the Python environment that runs OctoPrint, then run:

    ```bash
    python -m pip install https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower/archive/v0.1.2.zip
    ```

    Restart OctoPrint using your installation's service or process manager.

=== "Source checkout"

    With OctoPrint installed in the active environment:

    ```bash
    git clone https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower.git
    cd OctoPrint-HomeAssistantPower
    python -m pip install -e ".[develop]"
    ```

    This installs the checkout and test dependencies. See [Development](development.md) for an isolated development environment.

## Verify the installation

Run in OctoPrint's Python environment:

```bash
python -m pip show OctoPrint-HomeAssistantPower
```

For the release archive above, the package metadata includes:

```text
Name: OctoPrint-HomeAssistantPower
Version: 0.1.2
```

After restarting, confirm **Home Assistant Power** appears in Settings and complete [Getting started](getting-started.md).

## Upgrading

The plugin registers a GitHub-release update source with OctoPrint's Software Update plugin. Use an offered release update and restart OctoPrint. For a source checkout, update the checkout and repeat the editable install command. Back up OctoPrint settings and the plugin data folder before upgrading if you need to preserve credentials and energy history.

## Uninstalling

Disable post-print automation, then uninstall **Home Assistant Power** through Plugin Manager and restart. For a manual installation, run this in OctoPrint's environment:

```bash
python -m pip uninstall OctoPrint-HomeAssistantPower
```

Uninstalling the package does not itself revoke the Home Assistant token. Revoke it from your Home Assistant profile if nothing else uses it. The plugin implements no custom cleanup routine for saved settings or history.
