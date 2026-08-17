## Building with Fredgar UI

A dense, professional design system for financial data — SEC EDGAR filings, XBRL facts, FRED macro series. Prefer compact, information-rich layouts over airy marketing ones.

### Wrap the tree in `DesignSystemProvider`

`AppShell`, `CompanySearch`, and `CompanyMultiSelect` read from a router and a TanStack Query client; `AppShell` also reads app state. Without the provider they throw or render blank. It ships in `_ds_bundle.js` (no card of its own):

```jsx
const { DesignSystemProvider, Card, Button } = window.FredgarUI;

<DesignSystemProvider>
  <Card><div className="card-pad"><Button variant="primary">Sync</Button></div></Card>
</DesignSystemProvider>
```

Purely presentational components (everything in Primitives, Feedback, Charts, Icons) need no context, but wrapping them anyway is harmless.

### Theming

Light and dark both ship. Set `data-theme="light"` or `data-theme="dark"` on `<html>`; with neither, the system follows `prefers-color-scheme`. Never hardcode a hex — every color must come from a token so both themes work.

### Styling idiom: semantic classes + CSS variables

This is **not** a utility-first system and **not** a props-based one. Components carry their own classes; for your own layout glue, use this vocabulary:

| Family | Class names |
|---|---|
| Layout | `row` `col` `grid` `grid-2` `grid-3` `grid-4` `grid-auto` `wrap` `between` `grow` `center` |
| Spacing | `gap-1`…`gap-5` `mt-2`…`mt-5` `card-pad` `card-body` |
| Text | `muted` `subtle` `caption` `text-sm` `text-xs` `text-right` `truncate` `nowrap` |
| Numbers | `num` (tabular + mono — use for every figure) `mono` `pos` `neg` `td-num` |
| Surfaces | `card` `card-head` `card-hover` `divider` `banner` `page` `page-header` |
| Controls | `btn` `btn-primary` `btn-ghost` `btn-danger` `btn-sm` `input` `select` `textarea` `field` `field-label` `kbd` `link-btn` |

Anything not in that list should be a token in an inline style, never an invented class name. Tokens: `--c-bg` `--c-surface` `--c-surface-2` `--c-surface-3` `--c-border` `--c-border-strong` `--c-text` `--c-text-muted` `--c-text-subtle` `--c-accent` `--c-accent-soft` `--c-accent-text` `--c-positive` `--c-negative` `--c-warning` `--c-info` (each semantic color also has a `-soft` background variant); spacing `--sp-1`(4px)…`--sp-7`(48px); type `--fs-xs`(11px)…`--fs-3xl`; `--radius-sm` `--radius` `--radius-lg`; `--shadow-sm` `--shadow` `--shadow-lg`; categorical chart colors `--viz-1`…`--viz-6`.

```jsx
<div className="row between gap-3" style={{ padding: 'var(--sp-4)' }}>
```

### Conventions that matter here

- Every numeric figure gets `className="num"` so columns align.
- Table money/percent columns use `align: 'right'` in the `DataTable` column def.
- Attach `Provenance` to any figure sourced from SEC or FRED — this system shows
  its work.
- Reach for `Query` rather than hand-rolling loading/error/empty branches.
- `Stat` renders its own card; don't nest it inside another `Card`.

### Where the truth lives

- `_ds/<folder>/styles.css` → `@import`s `fonts/fonts.css` and `_ds_bundle.css`.
**`_ds_bundle.css` is the real stylesheet** — read it for the exact rules behind any class above.
- `components/<group>/<Name>/<Name>.prompt.md` for per-component usage, and
  `<Name>.d.ts` for the prop contract.
