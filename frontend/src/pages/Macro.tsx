/** Macro workspace — a finance-grade view of FRED indicators.
 *  Categorize (theme rail) · filter (search/frequency) · group (Grid/Overlay/Table
 *  views) · drill (detail drawer) · adjust (time range, FRED units and frequency
 *  aggregation computed by the API, and a client-side Index=100). */
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useBundleObservations, useSeriesBundles } from '../lib/queries'
import { compact, cx, date } from '../lib/format'
import {
  AGGREGATION_OPTIONS,
  applyRange,
  applyTransform,
  FREQUENCY_OPTIONS,
  isLevelTransform,
  isPercentTransform,
  isRateUnit,
  parseTransform,
  RANGE_OPTIONS,
  seriesPoints,
  seriesStats,
  serverUnits,
  TRANSFORM_OPTIONS,
  type Change,
  type ChartPoint,
  type RangeKey,
  type RawPoint,
  type SeriesStats,
  type Transform,
} from '../lib/macro'
import type { BundleObservations, BundleSeriesMeta, FredAggregation, FredFrequency } from '../lib/types'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { PageHeader } from '../components/PageHeader'
import {
  Badge,
  Card,
  DataTable,
  Drawer,
  EmptyState,
  IconExternal,
  IconGlobe,
  IconSearch,
  Loading,
  Query,
  Segmented,
} from '../components/ui'
import { MultiLineChart, Sparkline, TrendChart } from '../components/ui/Chart'

type View = 'grid' | 'overlay' | 'table'
type Prepared = { meta: BundleSeriesMeta; ranged: RawPoint[]; chart: ChartPoint[]; stats: SeriesStats | null }

const VIZ = (i: number) => `var(--viz-${(i % 6) + 1})`

/** Value format for the chosen units: percentages carry a % sign. */
const fmtValue = (t: Transform) => (v: number | null) =>
  v == null ? '—' : isPercentTransform(t) ? `${v.toFixed(1)}%` : compact(v)
/** Period changes read as percent changes only for levels in non-rate units; otherwise as point changes. */
const showsPointChange = (t: Transform, units: string) => !isLevelTransform(t) || isRateUnit(units)
const optionLabel = <T extends string>(options: { value: T; label: string }[], v: T) =>
  options.find((o) => o.value === v)?.label ?? v

export function Macro() {
  useDocumentTitle('Macro Series')
  const bundles = useSeriesBundles()

  // Shareable workspace state lives in the URL (bundle/view/range/units/frequency/aggregation).
  const [params, setParams] = useSearchParams()
  const patch = (k: string, v: string) =>
    setParams((p) => { if (v) p.set(k, v); else p.delete(k); return p }, { replace: true })
  const oneOf = <T extends string>(v: string | null, allowed: readonly T[], def: T): T =>
    (allowed as readonly string[]).includes(v ?? '') ? ((v ?? '') as T) : def
  const slug = params.get('b') || 'core'
  const view = oneOf<View>(params.get('v'), ['grid', 'overlay', 'table'], 'grid')
  const range = oneOf<RangeKey>(params.get('r'), ['1', '3', '5', '10', 'max'], '5')
  const transform = parseTransform(params.get('t'))
  const frequency = oneOf<FredFrequency | ''>(params.get('f'), FREQUENCY_OPTIONS.map((o) => o.value), '')
  const aggregation = oneOf<FredAggregation>(params.get('a'), AGGREGATION_OPTIONS.map((o) => o.value), 'avg')
  const setSlug = (s: string) => patch('b', s)
  const setView = (v: View) => patch('v', v)
  const setRange = (r: RangeKey) => patch('r', r)
  const setTransform = (t: Transform) => patch('t', t === 'lin' ? '' : t)
  const setFrequency = (f: FredFrequency | '') => patch('f', f)
  const setAggregation = (a: FredAggregation) => patch('a', a === 'avg' ? '' : a)

  // Transient controls stay local.
  const [search, setSearch] = useState('')
  const [freq, setFreq] = useState('')
  const [overlaySel, setOverlaySel] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<BundleSeriesMeta | null>(null)

  // The API computes the FRED units and the frequency aggregation; Index=100 rebases levels here.
  const obs = useBundleObservations(slug, { units: serverUnits(transform), frequency, aggregation })

  return (
    <div className="page">
      <PageHeader
        title="Macro Series"
        desc="FRED economic indicators grouped by industry relevance — categorize, filter, overlay, and transform for analysis."
      />

      <Query q={bundles} isEmpty={(b) => b.results.length === 0} empty={<Card><EmptyState icon={<IconGlobe />} title="No series bundles" message="Run refresh_series_bundles (FRED_API_KEY required)." /></Card>}>
        {(b) => {
          const active = b.results.find((x) => x.slug === slug) ? slug : b.results[0].slug
          return (
            <div className="macro-grid">
              {/* Category rail */}
              <nav className="cat-rail">
                <div className="nav-group-label" style={{ padding: '0 8px 4px' }}>Themes</div>
                {b.results.map((x) => (
                  <button key={x.slug} className={cx('cat-item', active === x.slug && 'active')} onClick={() => { setSlug(x.slug); setDetail(null) }}>
                    <span className="truncate">{x.name}</span>
                  </button>
                ))}
              </nav>

              {/* Workspace */}
              <div className="col gap-4" style={{ minWidth: 0 }}>
                {obs.isPending ? <Loading label="Loading series…" /> : obs.isError ? <Card><EmptyState title="Failed to load" message={(obs.error as Error).message} /></Card> : obs.data ? (
                  <Workspace
                    data={obs.data}
                    view={view} setView={setView}
                    range={range} setRange={setRange}
                    transform={transform} setTransform={setTransform}
                    frequency={frequency} setFrequency={setFrequency}
                    aggregation={aggregation} setAggregation={setAggregation}
                    search={search} setSearch={setSearch}
                    freq={freq} setFreq={setFreq}
                    overlaySel={overlaySel} setOverlaySel={setOverlaySel}
                    onDetail={setDetail}
                  />
                ) : null}
              </div>
            </div>
          )
        }}
      </Query>

      <Drawer open={!!detail} onClose={() => setDetail(null)} title={detail?.title} sub={detail ? `${detail.external_id}${detail.frequency ? ` · ${detail.frequency}` : ''}` : undefined}>
        {detail && obs.data && <SeriesDetail meta={detail} data={obs.data} range={range} transform={transform} />}
      </Drawer>
    </div>
  )
}

function Workspace(props: {
  data: BundleObservations
  view: View; setView: (v: View) => void
  range: RangeKey; setRange: (r: RangeKey) => void
  transform: Transform; setTransform: (t: Transform) => void
  frequency: FredFrequency | ''; setFrequency: (f: FredFrequency | '') => void
  aggregation: FredAggregation; setAggregation: (a: FredAggregation) => void
  search: string; setSearch: (s: string) => void
  freq: string; setFreq: (f: string) => void
  overlaySel: Set<string>; setOverlaySel: (s: Set<string>) => void
  onDetail: (m: BundleSeriesMeta) => void
}) {
  const { data, view, range, transform, frequency, aggregation, search, freq, overlaySel } = props

  const prepared = useMemo<Prepared[]>(() => {
    return data.series.map((meta) => {
      const ranged = applyRange(seriesPoints(data, meta.external_id), range)
      return { meta, ranged, chart: applyTransform(ranged, transform), stats: seriesStats(ranged) }
    })
  }, [data, range, transform])

  const frequencies = useMemo(() => [...new Set(data.series.map((s) => s.frequency).filter(Boolean))].sort(), [data.series])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return prepared.filter((p) => {
      if (freq && p.meta.frequency !== freq) return false
      if (!q) return true
      return (
        p.meta.title.toLowerCase().includes(q) ||
        p.meta.external_id.toLowerCase().includes(q) ||
        p.meta.industries.some((i) => i.toLowerCase().includes(q))
      )
    })
  }, [prepared, search, freq])

  const overlay = useMemo(() => {
    const ids = new Set(filtered.map((p) => p.meta.external_id))
    const chosen = [...overlaySel].filter((id) => ids.has(id))
    return new Set(chosen.length ? chosen : filtered.slice(0, 6).map((p) => p.meta.external_id))
  }, [overlaySel, filtered])

  function toggleOverlay(id: string) {
    const next = new Set(overlay)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    props.setOverlaySel(next)
  }

  const hint = TRANSFORM_OPTIONS.find((t) => t.value === transform)?.hint
  const aggregated = frequency
    ? ` · ${optionLabel(FREQUENCY_OPTIONS, frequency)}, ${optionLabel(AGGREGATION_OPTIONS, aggregation).toLowerCase()} (series of a lower frequency keep their own)`
    : ''

  return (
    <>
      {data.description && <p className="caption" style={{ maxWidth: '95ch' }}>{data.description}</p>}

      {/* Toolbar */}
      <Card className="card-pad">
        <div className="row gap-3 wrap between">
          <div className="row gap-3 wrap">
            <div className="search-box" style={{ width: 220 }}>
              <IconSearch width={16} height={16} className="ico" />
              <input className="input" placeholder="Filter series…" value={search} onChange={(e) => props.setSearch(e.target.value)} />
            </div>
            <select className="select" style={{ width: 'auto' }} value={freq} onChange={(e) => props.setFreq(e.target.value)}>
              <option value="">All frequencies</option>
              {frequencies.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div className="row gap-3 wrap">
            <select className="select" style={{ width: 'auto' }} aria-label="Units" title={hint} value={transform} onChange={(e) => props.setTransform(e.target.value as Transform)}>
              {TRANSFORM_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <select className="select" style={{ width: 'auto' }} aria-label="Frequency" value={frequency} onChange={(e) => props.setFrequency(e.target.value as FredFrequency | '')}>
              {FREQUENCY_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            <select className="select" style={{ width: 'auto' }} aria-label="Aggregation" disabled={!frequency} value={aggregation} onChange={(e) => props.setAggregation(e.target.value as FredAggregation)}>
              {AGGREGATION_OPTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
            <Segmented value={range} options={RANGE_OPTIONS} onChange={props.setRange} />
            <Segmented value={view} options={[{ value: 'grid', label: 'Grid' }, { value: 'overlay', label: 'Overlay' }, { value: 'table', label: 'Table' }]} onChange={props.setView} />
          </div>
        </div>
        <div className="caption mt-2">{filtered.length} of {data.series.length} series · {hint}{aggregated}</div>
      </Card>

      {filtered.length === 0 ? (
        <Card><EmptyState title="No series match" message="Adjust the search or frequency filter." /></Card>
      ) : view === 'grid' ? (
        <GridView items={filtered} transform={transform} onDetail={props.onDetail} />
      ) : view === 'overlay' ? (
        <OverlayView items={filtered} overlay={overlay} toggle={toggleOverlay} transform={transform} />
      ) : (
        <TableView items={filtered} transform={transform} onDetail={props.onDetail} />
      )}
    </>
  )
}

// ---- Change cell ----
function fmtChange(c: Change, isRate: boolean): { text: string; cls: string } {
  const v = isRate ? c.abs : c.pct
  if (v == null) return { text: '—', cls: 'subtle' }
  const sign = v > 0 ? '+' : ''
  const text = isRate ? `${sign}${v.toFixed(2)}` : `${sign}${v.toFixed(1)}%`
  return { text, cls: v > 0 ? 'pos' : v < 0 ? 'neg' : 'muted' }
}
function ChangeText({ c, isRate }: { c: Change; isRate: boolean }) {
  const { text, cls } = fmtChange(c, isRate)
  return <span className={`num ${cls}`}>{text}</span>
}

// ---- Grid ----
function GridView({ items, transform, onDetail }: { items: Prepared[]; transform: Transform; onDetail: (m: BundleSeriesMeta) => void }) {
  const fmt = fmtValue(transform)
  return (
    <div className="grid grid-2">
      {items.map((p, i) => {
        const rate = showsPointChange(transform, p.meta.units)
        return (
          <Card key={p.meta.external_id} hover>
            <div className="card-head" style={{ alignItems: 'flex-start', cursor: 'pointer' }} onClick={() => onDetail(p.meta)}>
              <div className="grow" style={{ minWidth: 0 }}>
                <h3 style={{ fontSize: 'var(--fs-base)' }} className="truncate" title={p.meta.title}>{p.meta.title}</h3>
                <div className="caption mono">{p.meta.external_id}{p.meta.frequency ? ` · ${p.meta.frequency}` : ''}</div>
              </div>
              {p.stats && (
                <div className="text-right" style={{ flex: 'none' }}>
                  <div className="num" style={{ fontWeight: 650 }}>{fmt(transform === 'index' ? p.chart[p.chart.length - 1]?.y ?? null : p.stats.latest)}</div>
                  <div className="text-xs"><ChangeText c={p.stats.chg1y} isRate={rate} /> <span className="subtle">1Y</span></div>
                </div>
              )}
            </div>
            <div className="card-body" onClick={() => onDetail(p.meta)} style={{ cursor: 'pointer' }}>
              <TrendChart height={150} data={p.chart} color={VIZ(i)} fmt={fmt} />
              {p.meta.note && <p className="caption mt-2" style={{ lineHeight: 1.5 }}>{p.meta.note}</p>}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

// ---- Overlay ----
function OverlayView({ items, overlay, toggle, transform }: { items: Prepared[]; overlay: Set<string>; toggle: (id: string) => void; transform: Transform }) {
  const idx = new Map(items.map((p, i) => [p.meta.external_id, i]))
  const selected = items.filter((p) => overlay.has(p.meta.external_id))
  const series = selected.map((p) => ({
    id: p.meta.external_id,
    name: p.meta.title,
    color: VIZ(idx.get(p.meta.external_id) ?? 0),
    points: p.chart,
  }))
  return (
    <Card>
      <div className="card-head">
        <div><h3 style={{ fontSize: 'var(--fs-md)' }}>Overlay comparison</h3><div className="caption">{transform === 'lin' ? 'Tip: use Index (=100) or a percent change to compare different-scale series.' : `${selected.length} series overlaid`}</div></div>
      </div>
      <div className="card-body">
        {series.length === 0 ? <EmptyState title="Select series to overlay" /> : <MultiLineChart series={series} fmt={fmtValue(transform)} />}
        {/* Toggle chips */}
        <div className="row gap-2 wrap mt-4">
          {items.map((p) => {
            const on = overlay.has(p.meta.external_id)
            return (
              <button
                key={p.meta.external_id}
                className={cx('badge', on && 'badge-accent')}
                style={{ cursor: 'pointer', borderColor: on ? VIZ(idx.get(p.meta.external_id) ?? 0) : undefined }}
                onClick={() => toggle(p.meta.external_id)}
                title={p.meta.title}
              >
                <span className="dot" style={{ color: VIZ(idx.get(p.meta.external_id) ?? 0), opacity: on ? 1 : 0.4 }} />
                {p.meta.external_id}
              </button>
            )
          })}
        </div>
      </div>
    </Card>
  )
}

// ---- Table ----
/** Sort key for a change column: the figure the column shows (points or percent). */
function changeSortValue(p: Prepared, key: 'chg1m' | 'chg3m' | 'chg1y', transform: Transform): number {
  const c = p.stats?.[key]
  const v = showsPointChange(transform, p.meta.units) ? c?.abs : c?.pct
  return v ?? -Infinity
}

function TableView({ items, transform, onDetail }: { items: Prepared[]; transform: Transform; onDetail: (m: BundleSeriesMeta) => void }) {
  const fmt = fmtValue(transform)
  // Latest is the value the chart ends on: the API's (FRED units applied), or the index.
  const latest = (p: Prepared) => (transform === 'index' ? p.chart[p.chart.length - 1]?.y ?? null : p.stats?.latest ?? null)
  return (
    <Card>
      <DataTable<Prepared>
        rows={items}
        rowKey={(p) => p.meta.external_id}
        onRowClick={(p) => onDetail(p.meta)}
        initialSort={{ key: 'chg1y', dir: 'desc' }}
        columns={[
          { key: 'name', header: 'Series', render: (p) => <div style={{ minWidth: 0 }}><div className="truncate" style={{ fontWeight: 600, maxWidth: 320 }}>{p.meta.title}</div><div className="caption mono">{p.meta.external_id} · {p.meta.frequency}</div></div>, sortable: true, sortValue: (p) => p.meta.title },
          { key: 'latest', header: 'Latest', align: 'right', render: (p) => (p.stats ? fmt(latest(p)) : '—'), sortable: true, sortValue: (p) => latest(p) ?? -Infinity },
          { key: 'chg1m', header: '1M', align: 'right', render: (p) => p.stats ? <ChangeText c={p.stats.chg1m} isRate={showsPointChange(transform, p.meta.units)} /> : '—', sortable: true, sortValue: (p) => changeSortValue(p, 'chg1m', transform) },
          { key: 'chg3m', header: '3M', align: 'right', render: (p) => p.stats ? <ChangeText c={p.stats.chg3m} isRate={showsPointChange(transform, p.meta.units)} /> : '—', sortable: true, sortValue: (p) => changeSortValue(p, 'chg3m', transform) },
          { key: 'chg1y', header: '1Y', align: 'right', render: (p) => p.stats ? <ChangeText c={p.stats.chg1y} isRate={showsPointChange(transform, p.meta.units)} /> : '—', sortable: true, sortValue: (p) => changeSortValue(p, 'chg1y', transform) },
          { key: 'spark', header: 'Trend', render: (p) => <Sparkline data={p.chart} width={120} height={36} color={VIZ(0)} /> },
        ]}
      />
    </Card>
  )
}

// ---- Detail drawer body ----
function SeriesDetail({ meta, data, range, transform }: { meta: BundleSeriesMeta; data: BundleObservations; range: RangeKey; transform: Transform }) {
  const raw = useMemo(() => seriesPoints(data, meta.external_id), [data, meta.external_id])
  const ranged = useMemo(() => applyRange(raw, range), [raw, range])
  const chart = useMemo(() => applyTransform(ranged, transform), [ranged, transform])
  const stats = seriesStats(ranged)
  const rate = showsPointChange(transform, meta.units)
  const fmt = fmtValue(transform)
  const option = TRANSFORM_OPTIONS.find((t) => t.value === transform)

  return (
    <div className="col gap-4">
      <div className="row between wrap gap-2">
        <span className="caption" title={option?.hint}>Units: {option?.label} (set in the toolbar)</span>
        <a href={`https://fred.stlouisfed.org/series/${meta.external_id}`} target="_blank" rel="noreferrer" className="row gap-1 text-sm">FRED <IconExternal width={12} height={12} /></a>
      </div>
      <TrendChart height={260} data={chart} fmt={fmt} />
      {stats && (
        <div className="grid grid-4">
          {[
            { l: 'Latest', v: fmt(stats.latest), s: date(stats.latestDate) },
            { l: '1M', v: fmtChange(stats.chg1m, rate).text },
            { l: '3M', v: fmtChange(stats.chg3m, rate).text },
            { l: '1Y', v: fmtChange(stats.chg1y, rate).text },
            { l: `${range === 'max' ? '' : range + 'Y '}High`, v: fmt(stats.max) },
            { l: `${range === 'max' ? '' : range + 'Y '}Low`, v: fmt(stats.min) },
          ].map((x) => (
            <div key={x.l} className="stat" style={{ padding: 'var(--sp-2)' }}>
              <div className="stat-label">{x.l}</div>
              <div className="stat-value" style={{ fontSize: 'var(--fs-lg)' }}>{x.v}</div>
              {x.s && <div className="stat-sub">{x.s}</div>}
            </div>
          ))}
        </div>
      )}
      {meta.units && <div><span className="field-label">Units</span><div className="text-sm">{meta.units}</div></div>}
      {meta.note && <div><span className="field-label">Why it matters</span><p className="text-sm mt-1" style={{ lineHeight: 1.6 }}>{meta.note}</p></div>}
      {meta.industries.length > 0 && (
        <div><span className="field-label">Relevant to</span><div className="row gap-1 wrap mt-1">{meta.industries.map((ind, j) => <Badge key={j}>{ind}</Badge>)}</div></div>
      )}
    </div>
  )
}
