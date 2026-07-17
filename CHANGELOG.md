# Changelog

## [0.2.0](https://github.com/bamr87/fredgar-ai/compare/v0.1.0...v0.2.0) (2026-07-17)


### Features

* **ai:** default to Claude authenticated via a token, enabled by default ([23756ae](https://github.com/bamr87/fredgar-ai/commit/23756aed33752e81b6516cc958b3631e0ba1b548))
* **ai:** default to Claude via a token (enabled by default) + docs rebrand sweep ([9f79337](https://github.com/bamr87/fredgar-ai/commit/9f7933777a13ef0ebb5d10664c982dfe50ea37d3))
* **data:** serverless dataset — release-hosted warehouse DB, offline publishes ([ce27bff](https://github.com/bamr87/fredgar-ai/commit/ce27bffb7d002cd35dfa3c1cca4c279cc6f3ff04))
* **frontend:** company picker for leadership comparison ([e983f4e](https://github.com/bamr87/fredgar-ai/commit/e983f4e248fabf61c5164bcdc86028f9e3b1fbf7))
* **frontend:** CSV export (statements/facts) + filing-search highlighting ([8f89843](https://github.com/bamr87/fredgar-ai/commit/8f89843109770561eb608791d5291c3f247e07eb))
* **frontend:** deep-linkable Company-360 tab + Macro workspace state ([f30c3c9](https://github.com/bamr87/fredgar-ai/commit/f30c3c96da7ee223b98ca9e075e582f89f3d7dfa))
* **frontend:** full revamp — design system, TanStack Query, Company-360 ([5427c81](https://github.com/bamr87/fredgar-ai/commit/5427c817a45fdf4b7f410e279963b97e0e2a49cc))
* **frontend:** keyboard focus rings + Settings toasts/disconnect ([34dfabe](https://github.com/bamr87/fredgar-ai/commit/34dfabee2d904c81d4a200baf3028e0c6f5b26b2))
* **frontend:** keyboard-navigable tabs (WAI-ARIA pattern) ([7210cf7](https://github.com/bamr87/fredgar-ai/commit/7210cf732343a6d989f0288a94176dc659b0c872))
* **frontend:** loading skeletons + Company Explorer CSV export ([33b4fd5](https://github.com/bamr87/fredgar-ai/commit/33b4fd5aba232686e57864cff52adff7bede2d79))
* **frontend:** macro workspace (views/transforms/drill) + drill-down nav ([35e9d83](https://github.com/bamr87/fredgar-ai/commit/35e9d83a5f887e5bfd631a85b3b2428bebe7346e))
* **frontend:** print stylesheet + leadership AI-analyze toast ([4b5932a](https://github.com/bamr87/fredgar-ai/commit/4b5932a34263be233ccf08edce0e428471bf6f74))
* **frontend:** revenue trend on the Company-360 overview ([58674ec](https://github.com/bamr87/fredgar-ai/commit/58674ec757713f820c7e9c8cd890bbff3dcf7c70))
* **frontend:** UX infra (toasts, error boundary, ⌘K, titles) + dashboard ([6989e92](https://github.com/bamr87/fredgar-ai/commit/6989e92541fe25cfd585d60768b38e6e5040899e))
* Initialize Django project with API for SEC filings ([df880bb](https://github.com/bamr87/fredgar-ai/commit/df880bb7fe49909184b3f23791e888a9ad5666ae))
* **macro:** expand FRED to 262 series across 14 industry bundles + trend fix ([574c350](https://github.com/bamr87/fredgar-ai/commit/574c35096e8fef92341f3cd0b844d167e4d49ebe))
* rate-limited, resumable bulk EDGAR sync across all companies ([0f0f2f6](https://github.com/bamr87/fredgar-ai/commit/0f0f2f64c6f5d38bc245776c9d9fb9d1f846e022))
* secure, analytics-rich EDGAR platform + leadership AI analyzer ([9506070](https://github.com/bamr87/fredgar-ai/commit/9506070124dbbe28a2b876ebd2d7c1dd6a6c616e))
* **static-site:** publish FRED macro data on the GitHub Pages mirror ([6cbbfe7](https://github.com/bamr87/fredgar-ai/commit/6cbbfe732f2056d7ce48a28834be871da5496593))
* **static-site:** publish FRED macro data on the GitHub Pages mirror ([9bf8da4](https://github.com/bamr87/fredgar-ai/commit/9bf8da4dc4e22ea46e5ab8997a69d174afb3b840))
* **static-site:** publish public mirror to GitHub Pages ([e14ac80](https://github.com/bamr87/fredgar-ai/commit/e14ac80871e3efb9d3158aaff9f327a5ec83248d))
* **static-site:** publish the public mirror to GitHub Pages ([747a1db](https://github.com/bamr87/fredgar-ai/commit/747a1db1700a30037d9cc990c373534bcf5856ae))
* **static-site:** turn the GitHub Pages index into a landing/hero page ([7eb67e0](https://github.com/bamr87/fredgar-ai/commit/7eb67e0a966de73b833d9f47cb65c700a846bf44))
* **static-site:** turn the GitHub Pages index into a landing/hero page ([6757b2b](https://github.com/bamr87/fredgar-ai/commit/6757b2b65eee0d3c6091719f5bbd6ae46dff9f98))


### Bug Fixes

* **ci:** make docs Liquid-safe and smoke-test the Pages publish path in PR CI ([65cb05b](https://github.com/bamr87/fredgar-ai/commit/65cb05b274da0214dd6ab203b0f79791913648e0))
* **ci:** make docs Liquid-safe and smoke-test the Pages publish path in PR CI ([e34a185](https://github.com/bamr87/fredgar-ai/commit/e34a1856f2c23ff7fa682f6679d10564a6b4fd23))
* **ci:** unambiguous grep option split in the Liquid-safety check ([f37f10c](https://github.com/bamr87/fredgar-ai/commit/f37f10ca7e54c48faf2a05dcaac616a9d798dc36))
* **frontend:** address PR [#19](https://github.com/bamr87/fredgar-ai/issues/19) review — a11y, robustness, CSV-injection guard ([c661a8f](https://github.com/bamr87/fredgar-ai/commit/c661a8fd89113308ef70e54f7f89467bec599a29))
* **frontend:** mobile hamburger menu never showed (CSS source order) ([d631cb0](https://github.com/bamr87/fredgar-ai/commit/d631cb0f986699cec6cee26ef4cb4bbd5d2ca689))
* mypy-clean the timeseries concept-chain resolver ([43f7eb6](https://github.com/bamr87/fredgar-ai/commit/43f7eb624f3cd2ecd895804d7318315a227b30bf))
* **pages:** publish on every push to main so the mirror self-heals ([b9125ca](https://github.com/bamr87/fredgar-ai/commit/b9125caf443d89ed80773b1b241599a9a400e583))
* **pages:** publish on every push to main so the mirror self-heals ([7d5ee5b](https://github.com/bamr87/fredgar-ai/commit/7d5ee5b745c8d91b2fbb540e75b0c6e19e4fa409))
* register Postgres FTS lookup for /filings/search/ ([b2d4ba3](https://github.com/bamr87/fredgar-ai/commit/b2d4ba327124f7ea3ab42227596048d039f2b50a))
* resolve all mypy errors (typecheck job now clean) ([1476f95](https://github.com/bamr87/fredgar-ai/commit/1476f956d30289d2d3a6579a232d7ef4c7dae73e))
* **static-site:** address Copilot review on macro export ([a02566a](https://github.com/bamr87/fredgar-ai/commit/a02566ab7e71d31b5ef37f133bb696eb7706ac21))
* **static-site:** repair landing-page dead links, demo search, and dead code ([18b5a95](https://github.com/bamr87/fredgar-ai/commit/18b5a9552ac9e8af8e7aba4ecf2b0cbabea3cfb2))
* **static-site:** repair landing-page dead links, demo search, and dead code ([497e4ac](https://github.com/bamr87/fredgar-ai/commit/497e4acaca7ad0bf583a071ce52438ac883c2208))
* **static-site:** satisfy mypy in _site_links settings fallback ([8fa8ed8](https://github.com/bamr87/fredgar-ai/commit/8fa8ed86299462731b72175c5904561648bd2b30))


### Performance Improvements

* **frontend:** prefetch company data on row hover ([793a883](https://github.com/bamr87/fredgar-ai/commit/793a8838048d4297fed7ccc55da9f5564b0d3092))

## Changelog

All notable changes to this project are documented here. This file is maintained
automatically by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/).
