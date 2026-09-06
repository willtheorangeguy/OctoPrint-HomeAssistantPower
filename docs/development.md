# Development

<!-- markdownlint-disable MD046 -->
<!-- Material content tabs require indentation around fenced code blocks. -->

Install OctoPrint before installing this plugin: `setup.py` imports `octoprint_setuptools` from the OctoPrint environment.

## Set up a checkout

```bash
git clone https://github.com/willtheorangeguy/OctoPrint-HomeAssistantPower.git
cd OctoPrint-HomeAssistantPower
```

Use Python 3.12 to match one of the existing CI jobs.

=== "Windows"

    ```powershell
    py -3.12 -m venv .venv
    .venv/Scripts/python.exe -m pip install OctoPrint
    .venv/Scripts/python.exe -m pip install -e ".[develop]"
    .venv/Scripts/python.exe -m pytest
    ```

=== "macOS / Linux"

    ```bash
    python3.12 -m venv .venv
    .venv/bin/python -m pip install OctoPrint
    .venv/bin/python -m pip install -e ".[develop]"
    .venv/bin/python -m pytest
    ```

The `develop` extra installs `pytest>=7` and `requests-mock>=1.10`. Runtime requirements remain supplied by OctoPrint. See [Testing](testing.md) for focused runs and the limits of the automated suite.

## Exercise the interface

Enable OctoPrint's **Virtual Printer** plugin to exercise print-lifecycle events without printer hardware. Use a dedicated Home Assistant test entity, such as an `input_boolean`, for switching checks. This does not validate physical plug behavior or serial boot timing.

Verify settings save, navbar state, permission-limited access, countdown cancellation, and sensor display. When changing templates, check both the Settings pane and the normal OctoPrint page. The plugin declares automatic template escaping.

## Preview documentation

The preview scripts come from the shared MkDocs repository. They obtain `.mkdocs-shared`, stage its design system, and run MkDocs from this repository's root. Keep the documentation dependencies in an activated environment.

=== "Windows"

    ```powershell
    .venv/Scripts/Activate.ps1
    ./scripts/docs-serve.ps1
    ```

=== "macOS / Linux"

    ```bash
    source .venv/bin/activate
    bash scripts/docs-serve.sh
    ```

The default preview address is [localhost port 8000](http://127.0.0.1:8000). The first run needs network access and installs the shared documentation requirements if `mkdocs` is unavailable. If MkDocs is already installed, refresh the full dependency set explicitly after the shared checkout exists:

```bash
python -m pip install -r .mkdocs-shared/shared/requirements-docs.txt
```

For a build without a server:

=== "Windows"

    ```powershell
    ./scripts/docs-serve.ps1 -Build
    ```

=== "macOS / Linux"

    ```bash
    bash scripts/docs-serve.sh --build
    ```

Output goes into ignored `site/`. Shared stylesheets, JavaScript, favicon, and theme partials are generated assets. Commit project content and intentional overrides, rather than copied shared assets.

## Writing and contribution conventions

Follow the writing standard shipped as `docs/docs.instructions.md`: sentence-case headings, tagged code fences, examples grounded in source, and relative Markdown page links. `mkdocs.yml` inherits plugins and extensions; redeclaring either list would replace the shared list.

Keep plugin behavior changes separate from documentation findings. The repository's `docs/internal/known-issues.md` records defects discovered during documentation and is excluded from the site. Follow the account's [Contributing Guide](https://github.com/willtheorangeguy/.github/blob/main/CONTRIBUTING.md) and [Code of Conduct](https://github.com/willtheorangeguy/.github/blob/main/CODE_OF_CONDUCT.md).
