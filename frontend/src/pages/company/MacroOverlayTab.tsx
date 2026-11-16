/** Company metric vs macro series (FREDGAR-013): a company series and a stored FRED
 *  series aligned per fiscal period, on a dual-axis chart with a correlation badge and
 *  CSV export. Alignment runs server-side (GET /companies/{id}/macro-overlay/). */
import { useMemo, useState } from 'react'
import {
  useBundleObservations,
  useCompany,
  useDerivedMetrics,
  useMacroOverlay,
  useSeriesBundles,
} from '../../lib/queries'
import { byUnit, compact, date } from '../../lib/format'
import { formatDerivedMetric } from '../../lib/finance'
import { isRateUnit } from '../../lib/macro'
import { downloadCsv } from '../../lib/csv'
import {
  OVERLAY_CSV_COLUMNS,
  companySeriesOptions,
  correlationSummary,
  droppedReason,
  overlayChartRows,
  overlayCsvRows,
  storedSeries,
} from '../../lib/overlay'
import type { MacroOverlay, OverlayAgg } from '../../lib/types'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  ErrorState,
  IconDownload,
  IconGlobe,
  Loading,
  Query,
  Segmented,
} from '../../components/ui'
import { DualAxisChart } from '../../components/ui/Chart'

const AGG_OPTIONS: { value: OverlayAgg; label: string }[] = [
  { value: 'avg', label: 'Average' },
  { value: 'eop', label: 'End of period' },
]

const COMPANY_COLOR = 'var(--viz-1)'
const SERIES_COLOR = 'var(--viz-2)'

export function MacroOverlayTab({ id }: { id: number }) {
  const company = useCompany(id)
  const metrics = useDerivedMetrics(id)
  const bundles = useSeriesBundles()
  const [companyKey, setCompanyKey] = useState('concept:revenue')
  const [bundleSlug, setBundleSlug] = useState<string | null>(null)
  const [seriesPick, setSeriesPick] = useState('')
  const [agg, setAgg] = useState<OverlayAgg>('avg')

  const bundleList = bundles.data?.results ?? []
  const slug = bundleSlug ?? bundleList[0]?.slug ?? null
  const obs = useBundleObservations(slug)
  const seriesOptions = useMemo(() => (obs.data ? storedSeries(obs.data) : []), [obs.data])
  const seriesId = seriesOptions.some((s) => s.external_id === seriesPick) ? seriesPick : (seriesOptions[0]?.external_id ?? '')

  const options = useMemo(() => companySeriesOptions(metrics.data?.results ?? []), [metrics.data])
  const chosen = options.find((o) => o.value === companyKey) ?? options[0]
  const params = useMemo(
    () => (seriesId ? { metric: chosen.metric, concepts: chosen.concepts, series: seriesId, agg, annual: chosen.annual } : null),
    [chosen, seriesId, agg],
  )
  const overlay = useMacroOverlay(id, params)
  const ticker = company.data?.ticker || company.data?.cik || String(id)

  if (bundles.isError) return <Card><ErrorState error={bundles.error} /></Card>
  if (bundles.isSuccess && bundleList.length === 0) {
    return (
      <Card>
        <EmptyState icon={<IconGlobe />} title="No macro series stored" message="Run refresh_series_bundles (FRED_API_KEY required) to store FRED series, then overlay them here." />
      </Card>
    )
  }

  const exportCsv = () => {
    if (!overlay.data) return
    downloadCsv(`${ticker}-${overlay.data.company_series.key}-vs-${overlay.data.series.external_id}.csv`, overlayCsvRows(overlay.data), [...OVERLAY_CSV_COLUMNS])
  }

  return (
    <div className="col gap-4">
      <Card>
        <CardHeader
          title="Company vs macro"
          sub="Each fiscal period of the company, against the series aggregated over that same period"
          actions={
            <Button size="sm" variant="ghost" disabled={!overlay.data?.rows.length} onClick={exportCsv} title="Download CSV" aria-label="Download CSV">
              <IconDownload width={14} height={14} />
            </Button>
          }
        />
        <div className="card-body col gap-3">
          <div className="row gap-2 wrap">
            <label className="caption row gap-1">
              Company
              <select className="select" style={{ width: 'auto' }} value={chosen.value} onChange={(e) => setCompanyKey(e.target.value)} aria-label="Company series">
                {(['Reported (XBRL)', 'Derived metrics'] as const).map((group) => {
                  const inGroup = options.filter((o) => o.group === group)
                  return inGroup.length ? (
                    <optgroup key={group} label={group}>
                      {inGroup.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </optgroup>
                  ) : null
                })}
              </select>
            </label>
            <label className="caption row gap-1">
              Theme
              <select className="select" style={{ width: 'auto' }} value={slug ?? ''} onChange={(e) => { setBundleSlug(e.target.value); setSeriesPick('') }} aria-label="Series bundle">
                {bundleList.map((b) => <option key={b.slug} value={b.slug}>{b.name}</option>)}
              </select>
            </label>
            <label className="caption row gap-1">
              Series
              <select className="select" style={{ width: 'auto', maxWidth: 320 }} value={seriesId} onChange={(e) => setSeriesPick(e.target.value)} aria-label="Macro series" disabled={seriesOptions.length === 0}>
                {seriesOptions.map((s) => <option key={s.external_id} value={s.external_id}>{s.external_id} · {s.title}</option>)}
              </select>
            </label>
            <Segmented value={agg} options={AGG_OPTIONS} onChange={setAgg} />
          </div>

          {obs.isError ? (
            <ErrorState error={obs.error} />
          ) : !seriesId && (bundles.isPending || obs.isPending) ? (
            <Loading label="Loading series…" />
          ) : !seriesId ? (
            <EmptyState title="No stored series in this theme" message="Pick another theme, or sync this bundle (sync_series_bundle)." />
          ) : (
            <Query
              q={overlay}
              isEmpty={(o) => o.rows.length === 0}
              empty={<NoAlignedPeriods overlay={overlay.data} />}
              loadingLabel="Aligning periods…"
            >
              {(o) => <OverlayResult o={o} label={chosen.label} />}
            </Query>
          )}
        </div>
      </Card>
    </div>
  )
}

function companyFmt(o: MacroOverlay) {
  return (v: number) =>
    o.company_series.source === 'metric' ? formatDerivedMetric(o.company_series.key, v, o.company_series.unit) : byUnit(v, o.company_series.unit)
}

function seriesFmt(o: MacroOverlay) {
  return (v: number) => (isRateUnit(o.series.units) ? `${v.toFixed(2)}%` : compact(v))
}

function OverlayResult({ o, label }: { o: MacroOverlay; label: string }) {
  const corr = correlationSummary(o.correlation.r, o.correlation.n)
  const fmtCompany = companyFmt(o)
  const fmtSeries = seriesFmt(o)
  return (
    <div className="col gap-3">
      <div className="row gap-2 wrap">
        <Badge tone={corr.tone}>{corr.text}</Badge>
        <span className="caption">
          {o.series.title || o.series.external_id}
          {o.series.units ? ` (${o.series.units})` : ''} · {o.alignment.aggregation === 'eop' ? 'end of period' : 'average'} per fiscal period
        </span>
      </div>
      <DualAxisChart
        data={overlayChartRows(o)}
        left={{ name: label, color: COMPANY_COLOR, fmt: fmtCompany }}
        right={{ name: o.series.external_id, color: SERIES_COLOR, fmt: fmtSeries }}
      />
      <DataTable
        compact
        rows={[...o.rows].reverse()}
        rowKey={(r) => r.period_end}
        columns={[
          { key: 'start', header: 'Period start', render: (r) => date(r.period_start) },
          { key: 'end', header: 'Period end', render: (r) => date(r.period_end) },
          { key: 'company', header: label, align: 'right', render: (r) => fmtCompany(r.company_value) },
          { key: 'series', header: o.series.external_id, align: 'right', render: (r) => fmtSeries(r.series_value) },
          { key: 'n', header: 'Obs.', align: 'right', render: (r) => r.series_observations },
        ]}
      />
      <p className="caption">
        {o.alignment.description}
        {o.alignment.dropped.length > 0 && ` ${o.alignment.dropped.length} period(s) not aligned.`}
        {' '}A high r between two trending levels is expected and does not by itself mean the series move together.
      </p>
    </div>
  )
}

function NoAlignedPeriods({ overlay }: { overlay: MacroOverlay | undefined }) {
  const dropped = overlay?.alignment.dropped ?? []
  const reasons = [...new Set(dropped.map((d) => droppedReason(d.reason)))]
  return (
    <EmptyState
      title="No aligned periods"
      message={
        dropped.length
          ? `${dropped.length} fiscal period(s) could not be aligned: ${reasons.join('; ')}.`
          : 'This company has no values for the selected series yet. Sync facts, or compute metrics (admin).'
      }
    />
  )
}
