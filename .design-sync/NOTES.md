# design-sync notes — fredgar-ai frontend

Repo-specific gotchas for `/design-sync`. Read this before re-syncing.

## Running it

From the repo root, after staging the skill's scripts into `.ds-sync/` and installing its deps there:

```sh
cd frontend && npx tsc -p tsconfig.ds.json && cd ..     # cfg.buildCmd — regenerates types/
NODE_PATH=.ds-sync/node_modules node .ds-sync/resync.mjs \
  --config .design-sync/config.json --node-modules frontend/node_modules \
  --entry frontend/design-system.entry.tsx --out ./ds-bundle
```

Both `--entry` and `--node-modules` are required every run — this package has no library `dist/`, and omitting `--entry` makes the converter look for `frontend/node_modules/frontend`, which does not exist. `NODE_PATH` is needed because playwright lives in `.ds-sync/node_modules`, not the repo root.

## CI gotchas this repo enforces

These bit during the first sync — they are not design-sync problems, they are repo standards.

- **`tools/unwrap-prose.py --check` (the `oneline` CI job) rejects hard-wrapped markdown.** Anything you add under `.design-sync/` — `NOTES.md`, `conventions.md`, doc stubs — must be one long line per paragraph. Run `python3 tools/unwrap-prose.py --write <files>` before committing.
- **`frontend/types/` is eslint-ignored** in `eslint.config.js`; it is generated output and trips `@typescript-eslint/no-explicit-any`. Don't remove that ignore.
- **`design-system.entry.tsx` carries a file-level `react-refresh/only-export-components` disable.** The rule cannot verify `export *` and the file is outside the app's module graph anyway.
- `npm run lint`, `npm run build`, `npm test`, and `ruff check src tests` all pass on this branch — re-run them after touching anything in `frontend/`.

## Shape of this repo

- The design system is an **application**, not a published library:
`frontend/package.json` is `private: true` and there is no library `dist/`. Everything below exists to give the converter a library-shaped surface.
- `frontend/design-system.entry.tsx` — the DS entry, committed. Re-exports the
`src/components/ui` barrel, `Chart.tsx`, the app-level components, `AppShell`, the toast module, and `ApiError`. It also defines `DesignSystemProvider`. It lives at the **package root, not in `src/`**, deliberately: `tsconfig.app.json` only includes `src/`, so `npm run build` never sees it and the app bundle is unaffected. The converter's `PKG_DIR` is resolved by walking up from `--entry` to the nearest `package.json` with a name, so the entry has to sit inside `frontend/` — do not move it to the repo root or `.design-sync/`.
- `frontend/tsconfig.ds.json` + `"types"` in `frontend/package.json` — a
declaration-only build emitting `frontend/types/`. **This is load-bearing.** Without it the converter finds no `.d.ts` tree and every emitted `<Name>Props` degrades to `[key: string]: unknown`, which is a useless contract for the design agent. `cfg.buildCmd` runs it; `frontend/types/` is gitignored and regenerated.
- `npm run build:ds-types` is the same command as an npm script.

## Config decisions

- `pkg` is `"frontend"` (the real package.json name), so previews and
`.prompt.md` examples import from `'frontend'`. Nothing actually resolves that specifier — real app code imports `./components/ui`. The conventions header tells the design agent to use `window.FredgarUI.*`, which is what the bundle provides. Don't "fix" this to an invented scope like `@fredgar/ui`.
- `componentSrcMap` is sparse and excludes two bundle exports from the card
index: `DesignSystemProvider` (preview wrapper) and `ApiError` (a class, not a component — exported because `ErrorState` branches on `instanceof ApiError`, which is the only way its 403/404/429 states are truthful).
- `docsDir` → `.design-sync/docs/`, 51 committed stubs whose frontmatter
`category` produces the nine picker groups (Primitives, Feedback, Data, Navigation, Charts, Overlays, Search, Layout, Icons). Without them everything lands in `general`. **Adding a component means adding a stub**, or it falls back to `general`.
- `dtsPropsFor` covers 10 components. Two reasons: the extractor's
`[DTS_STYLE_SYSTEM]` filter strips `@types/react` prop bags, which silently removed `onClick`/`disabled`/`type` from `Button`; and generic or locally-declared types (`Column<T>`, `TabDef`, `Point`, `OverlaySeries`, `PickedCompany`, `UseQueryResult`) emit as undefined identifiers. The overrides inline those shapes.
- `overrides`: `Drawer`, `ToastProvider`, `AppShell` are `cardMode: single` with
explicit viewports (overlays and full-page chrome escape a grid cell); `Stat` is `cardMode: column` after a `[GRID_OVERFLOW]` warn.

## Fonts

- `--font-sans` names `'Inter'`, but **the app never loads it** — no
`@font-face`, no `<link>`. The live app therefore renders in `system-ui`. The sync ships Inter (variable, SIL OFL) from `.design-sync/fonts/` via `cfg.extraFonts` so previews and generated designs match the declared intent. Fixing the app itself is a separate change nobody has made yet.
- `[FONT_MISSING] "JetBrains Mono"` is an **accepted substitute**, agreed with
the user. It sits third in the `--font-mono` stack behind `ui-monospace` and `'SF Mono'`, so it is effectively never selected. Do not chase it.

## Known render warns

Warns triaged as legitimate — a warn *not* on this list is new, look at it.

- `[RENDER_THIN] Drawer … rendered height is 0px` — `.drawer-root` is
`position: fixed`, so it contributes no height to the measured root. The screenshot shows a fully composed panel. Benign.
- **recharts series look half-drawn in `_screenshots/review/`** (`TrendChart`,
`MultiLineChart`). `package-capture.mjs` calls `page.clock.setFixedTime(...)`, which stalls recharts' JS-driven mount animation partway. Verified complete by rendering the same card with a real clock and a 4s wait — the full series draws. `Sparkline` is unaffected because it sets `isAnimationActive={false}`. The components expose no way to disable animation, and a CSS `animation-duration: 0s` override does **not** help (react-smooth animates in JS, not CSS) — that was tried and reverted. Not a defect: the product renders these cards as live HTML with a real clock.

## Preview gotchas

- **Do not import `react-router-dom` in a preview.** A preview-side import is a
second copy of the library and shares no context with the router bundled into `_ds_bundle.js`. Wrapping `AppShell` in `<Routes>` to fill its `<Outlet/>` rendered a completely blank card. `AppShell.tsx` is deliberately just `<AppShell />`; its empty content area is the unrouted outlet.
- `ToastProvider` pushes one toast of each kind on mount and reserves
`minHeight: 460` — the toaster is `position: fixed` bottom-right and the card otherwise collapses to the trigger row and captures the stack clipped. An earlier `setInterval` re-push stacked nine toasts; one push is enough because capture happens well inside the 3.5s auto-dismiss.
- `CompanySearch` / `CompanyMultiSelect` render their resting state only. Their
dropdowns open on input, and `DesignSystemProvider` seeds only `['ready'] = {status:'ok'}` (which is what lights AppShell's "API online" indicator). No network is available during capture; the components degrade to an empty result list rather than erroring.

## Re-sync risks

Watch these — they can go stale silently:

- **`dtsPropsFor` is a hand-maintained copy of 10 prop contracts.** If
`Button`, `DataTable`, `Tabs`, `Segmented`, `Query`, the four charts, or `CompanyMultiSelect` change their props upstream, the emitted `.d.ts` will keep describing the old shape and nothing will flag it. Diff these against `frontend/types/` after any change to those components.
- **`.design-sync/docs/*.md` descriptions are hand-written** and will drift from
  the components they describe.
- **Preview fixtures are illustrative, not live data** — the SEC figures in
`previews/` (FY2024 revenue, margins, CIKs) were written by hand and are not refreshed from the warehouse.
- **`frontend/types/` must be regenerated before the converter runs.** A stale
  tree silently produces stale props. `cfg.buildCmd` does it; run it.
- **Never uploaded.** This repo has been converted and verified locally only —
`DesignSync` could not authorize in the environment where this ran, so there is no `projectId` in the config and no `_ds_sync.json` anchor on any project. The next run with authorization does a **first-time upload**: it creates the project, records `projectId`, and re-verifies everything (there is no anchor to skip against). All 51 authored previews and their config carry forward, so the expensive part is already done.
- Toolchain assumptions at time of writing: node with `npm ci` from
`frontend/package-lock.json`; converter deps `esbuild` + `ts-morph` + `@types/react` in `.ds-sync/`; **playwright 1.56.0**, chosen because the preinstalled chromium in `/opt/pw-browsers` is build **1194** and 1.56.0 is the release that pins it. A different image will need a different pin — check `node_modules/playwright-core/browsers.json` against the cached `chromium-<build>` directory name.
