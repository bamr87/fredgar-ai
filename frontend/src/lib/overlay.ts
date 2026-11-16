/** Pure helpers for the company Macro tab (FREDGAR-013): the company-series options,
 *  the series picker, chart rows, CSV rows and the correlation label. The alignment
 *  itself happens server-side (GET /companies/{id}/macro-overlay/). */
import { humanize } from './format'
import { TREND_CONCEPTS } from './finance'
import type { BundleObservations, BundleSeriesMeta, DerivedMetric, MacroOverlay } from './types'

/** One choice in the company-series picker: an XBRL concept chain or a derived metric. */
export type CompanySeriesOption = {
  value: string
  label: string
  group: 'Reported (XBRL)' | 'Derived metrics'
  concepts?: string[]
  metric?: string
  annual: boolean
}

/** Concept chains from the Financials trend picker, then the company's own derived metrics.
 *  Metrics are aligned on full fiscal years (`annual`), since quarter-end metrics mix
 *  quarter and year-to-date inputs. */
export function companySeriesOptions(metrics: Pick<DerivedMetric, 'key'>[]): CompanySeriesOption[] {
  const concepts: CompanySeriesOption[] = TREND_CONCEPTS.map((c) => ({
    value: `concept:${c.key}`,
    label: c.label,
    group: 'Reported (XBRL)',
    concepts: c.concepts,
    annual: c.annual,
  }))
  const keys = [...new Set(metrics.map((m) => m.key))].sort()
  const derived: CompanySeriesOption[] = keys.map((key) => ({
    value: `metric:${key}`,
    label: humanize(key),
    group: 'Derived metrics',
    metric: key,
    annual: true,
  }))
  return [...concepts, ...derived]
}

/** The bundle's series that have stored observations (the overlay never calls FRED). */
export function storedSeries(obs: BundleObservations): BundleSeriesMeta[] {
  const stored = new Set(obs.observations.map((o) => o.series))
  return obs.series.filter((s) => stored.has(s.external_id))
}

export type OverlayChartRow = { x: string; left: number | null; right: number | null }

/** One chart row per aligned fiscal period: company on the left axis, series on the right. */
export function overlayChartRows(o: MacroOverlay): OverlayChartRow[] {
  return [...o.rows]
    .sort((a, b) => a.period_end.localeCompare(b.period_end))
    .map((r) => ({ x: r.period_end, left: r.company_value, right: r.series_value }))
}

export const OVERLAY_CSV_COLUMNS = [
  'period_start',
  'period_end',
  'company_series',
  'company_value',
  'company_unit',
  'series_id',
  'series_value',
  'series_units',
  'aggregation',
  'series_observations',
] as const

/** Flat CSV rows (one per aligned fiscal period) for `downloadCsv`. */
export function overlayCsvRows(o: MacroOverlay): Record<string, unknown>[] {
  return o.rows.map((r) => ({
    period_start: r.period_start ?? '',
    period_end: r.period_end,
    company_series: o.company_series.key,
    company_value: r.company_value,
    company_unit: o.company_series.unit ?? '',
    series_id: o.series.external_id,
    series_value: r.series_value,
    series_units: o.series.units,
    aggregation: o.alignment.aggregation,
    series_observations: r.series_observations,
  }))
}

export type CorrelationSummary = { text: string; tone: 'pos' | 'neg' | 'default' }

/** Badge text for Pearson r: strength by |r| (0.7 strong, 0.4 moderate, 0.2 weak) and sign. */
export function correlationSummary(r: number | null, n: number): CorrelationSummary {
  if (r === null || !Number.isFinite(r)) {
    return { text: `r n/a · n = ${n}${n < 3 ? ' (needs 3+ aligned periods)' : ''}`, tone: 'default' }
  }
  const a = Math.abs(r)
  const strength = a >= 0.7 ? 'strong' : a >= 0.4 ? 'moderate' : a >= 0.2 ? 'weak' : 'no'
  const direction = strength === 'no' ? 'correlation' : r > 0 ? 'positive' : 'negative'
  const tone = strength === 'no' ? 'default' : r > 0 ? 'pos' : 'neg'
  return { text: `r = ${r.toFixed(2)} · ${strength} ${direction} · n = ${n}`, tone }
}

/** Plain-language reason a fiscal period did not align. */
export function droppedReason(reason: string): string {
  const reasons: Record<string, string> = {
    no_observations: 'no series observation inside the period',
    series_starts_late: 'the series starts after the period begins',
    series_ends_early: 'the series ends before the period ends',
    gap: 'a missing observation inside the period',
    series_too_short: 'the series has fewer than two observations',
    no_fiscal_window: 'no fiscal period could be inferred',
  }
  return reasons[reason] ?? reason
}
