# Releasing

> How a fredgar-ai release happens: release-please turns Conventional Commit PR titles into a release PR, and merging that PR tags and publishes it.

This repo uses the standardized [bamr87 release pipeline](https://github.com/bamr87/.github#readme). Nobody bumps a version or edits `CHANGELOG.md` by hand — [release-please](https://github.com/googleapis/release-please) does both.

## How a release happens

1. Land changes through PRs with **[Conventional Commit](https://www.conventionalcommits.org/)** titles (`fix:` → patch, `feat:` → minor, `feat!:` or `BREAKING CHANGE:` → major).
2. On each merge to `main`, [`.github/workflows/release.yml`](../.github/workflows/release.yml) runs release-please, which opens or updates a **release PR** that bumps the version and rewrites `CHANGELOG.md`.
3. **Merge the release PR** when you are ready to ship. That tags `vX.Y.Z`, creates the GitHub Release, and publishes it: the shared `publish.yml` pushes the container image to GHCR, and the `pypi` job in `release.yml` uploads the sdist and wheel to [PyPI](https://pypi.org/p/fredgar-ai).

## PyPI

The `pypi` job checks out the release tag, builds with `python -m build` on Python 3.12, and uploads through [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no API token). It is defined in `release.yml` itself because PyPI rejects a token minted inside a reusable workflow (`invalid-publisher`), so the shared `publish.yml` cannot do the upload. The shared workflow has no input to turn its own `🐍 PyPI` job off, so that job still runs on every release and fails at the token exchange without uploading anything.

release-please (`release-type: simple`) does not bump `version` in `pyproject.toml`, so the job writes the released version into its checkout before building and stops if the file does not then carry it. Nothing is committed back.

The trusted publisher on pypi.org must match the job exactly:

| Field | Value |
| --- | --- |
| PyPI project name | `fredgar-ai` |
| Owner | `bamr87` |
| Repository name | `fredgar-ai` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

While the project does not exist on PyPI, add it as a *pending* publisher (pypi.org → Your account → Publishing); the first upload creates the project. GitHub creates the `pypi` environment the first time the job runs.

## What is tracked

- Config: [`release-please-config.json`](../release-please-config.json) (`release-type: simple`, changelog `CHANGELOG.md`).
- Current version: [`.release-please-manifest.json`](../.release-please-manifest.json).
- The markdown prose gate (`make prose`, CI's `markdown-oneline` job) skips `CHANGELOG.md`: release-please writes it in its own wrapped format, so a reflow would be overwritten on the next release and editing it by hand is forbidden anyway.

## Setup

- No secrets are required: GHCR uses the workflow token and PyPI uses the trusted publisher above. An optional `RELEASE_PLEASE_TOKEN` PAT lets the release PR trigger CI.
- To re-run release-please without a code change, merge any pending release PR or push an empty `chore: release` commit.
