# Releasing

> How a fredgar-ai release happens: release-please turns Conventional Commit PR titles into a release PR, and merging that PR tags and publishes it.

This repo uses the standardized [bamr87 release pipeline](https://github.com/bamr87/.github#readme). Nobody bumps a version or edits `CHANGELOG.md` by hand — [release-please](https://github.com/googleapis/release-please) does both.

## How a release happens

1. Land changes through PRs with **[Conventional Commit](https://www.conventionalcommits.org/)** titles (`fix:` → patch, `feat:` → minor, `feat!:` or `BREAKING CHANGE:` → major).
2. On each merge to `main`, [`.github/workflows/release.yml`](../.github/workflows/release.yml) runs release-please, which opens or updates a **release PR** that bumps the version and rewrites `CHANGELOG.md`.
3. **Merge the release PR** when you are ready to ship. That tags `vX.Y.Z`, creates the GitHub Release, and the shared `publish.yml` job publishes it (GitHub Releases only).

## What is tracked

- Config: [`release-please-config.json`](../release-please-config.json) (`release-type: simple`, changelog `CHANGELOG.md`).
- Current version: [`.release-please-manifest.json`](../.release-please-manifest.json).

## Setup

- No secrets are required. An optional `RELEASE_PLEASE_TOKEN` PAT lets the release PR trigger CI.
- To re-run release-please without a code change, merge any pending release PR or push an empty `chore: release` commit.
