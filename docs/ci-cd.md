# CI/CD

Plugin tests run in this repository. Documentation build, lint, and deployment logic come from reusable workflows in `willtheorangeguy/mkdocs`.

## Workflows

| Workflow | Trigger | Result |
| --- | --- | --- |
| `test.yml` | Pushes and pull requests | Install OctoPrint and the plugin's `develop` extra, then run pytest on Python 3.9 and 3.12. |
| `docs-lint.yml` | Pull requests touching docs, source used by the Python reference, site configuration, included license, or documentation helpers; manual dispatch | Shared Markdown lint, strict MkDocs build, and external link check. Does not deploy. |
| `docs.yml` | Relevant changes on `main` or `master`; manual dispatch | Shared build and GitHub Pages deployment. |

The documentation callers use the shared workflows at `@main`. Shared dependency and theme updates therefore apply on the next run. The local configuration inherits `.mkdocs-shared/shared/mkdocs.base.yml` and keeps the shared plugin and extension lists intact.

## Pages destination

The configured canonical URL is `https://williamvdg.me/OctoPrint-HomeAssistantPower/`. The account's Pages custom domain is `williamvdg.me`. This repository has no existing app at the Pages root, so no `docs_subpath` is needed.

GitHub Pages must use **GitHub Actions** as its publishing source before the deployment job can publish. Adding a workflow alone does not enable that repository setting. Once the workflow exists on the default branch and Pages is configured, a maintainer can rebuild with:

```bash
gh workflow run docs.yml --repo willtheorangeguy/OctoPrint-HomeAssistantPower
```

This page describes the deployment configuration, not proof that a particular revision is live.

## Permissions and concurrency

The deploy caller grants `contents: read`, `pages: write`, and `id-token: write`. Its `pages` concurrency group does not cancel in-progress deployments. The lint caller needs only `contents: read`.

## Diagnose a docs failure

- **Missing `.mkdocs-shared` locally:** run the preview helper from [Development](development.md#preview-documentation).
- **Missing included file:** check the snippet target. The license page includes the existing root `LICENSE` file.
- **Missing page or anchor:** update the link and `nav` when renaming a page.
- **Macro parsing failure:** wrap literal Jinja syntax in a raw block, following `docs/docs.instructions.md`.
- **Dependency or reusable-workflow failure:** inspect the shared repository revision used by that run.
- **Pages deployment failure:** check the repository publishing source and caller permissions.
