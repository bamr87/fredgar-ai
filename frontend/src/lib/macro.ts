/** Pure helpers for the macro workspace: range windows, the Units control (FRED's units,
 *  applied by the API, plus a client-side Index=100 rebase), and period-change stats.
 *  Frequency-agnostic via date-based lookups. */
import type { BundleObservations, FredAggregation, FredFrequency, FredUnits } from './types'

export type RawPoint = { date: string; value: number }
export type ChartPoint = { x: string; y: number | null }
export type RangeKey = '1' | '3' | '5' | '10' | 'max'
/** The Units control: every FRED unit (computed server-side), plus `index`, the levels
 *  rebased to 100 at the window start in the browser, as FRED's own graph offers. */
export type Transform = FredUnits | 'index'

export const RANGE_OPTIONS: { value: RangeKey; label: string }[] = [
  { value: '1', label: '1Y' },
  { value: '3', label: '3Y' },
  { value: '5', label: '5Y' },
  { value: '10', label: '10Y' },
  { value: 'max', label: 'Max' },
]

/** Labels and formulas as FRED documents them; n = observations per year. */
export const TRANSFORM_OPTIONS: { value: Transform; label: string; hint: string }[] = [
  { value: 'lin', label: 'Levels', hint: 'Values as reported' },
  { value: 'index', label: 'Index (=100)', hint: 'Levels rebased to 100 at the window start' },
  { value: 'chg', label: 'Change', hint: 'Change: x(t) − x(t−1)' },
  { value: 'ch1', label: 'Change from year ago', hint: 'Change from year ago: x(t) − x(t−n)' },
  { value: 'pch', label: 'Percent change', hint: 'Percent change: (x(t) / x(t−1) − 1) × 100' },
  { value: 'pc1', label: 'Percent change from year ago', hint: 'Percent change from year ago: (x(t) / x(t−n) − 1) × 100' },
  { value: 'pca', label: 'Compounded annual rate of change', hint: 'Compounded annual rate: ((x(t) / x(t−1))^n − 1) × 100' },
  { value: 'cch', label: 'Continuously compounded rate of change', hint: 'Continuously compounded: (ln x(t) − ln x(t−1)) × 100' },
  { value: 'cca', label: 'Continuously compounded annual rate of change', hint: 'Continuously compounded annual: (ln x(t) − ln x(t−1)) × 100 × n' },
  { value: 'log', label: 'Natural log', hint: 'Natural log: ln x(t)' },
]

/** Aggregation targets ('' keeps each series at its own frequency). */
export const FREQUENCY_OPTIONS: { value: FredFrequency | ''; label: string }[] = [
  { value: '', label: 'Native frequency' },
  { value: 'w', label: 'Weekly, ending Friday' },
  { value: 'm', label: 'Monthly' },
  { value: 'q', label: 'Quarterly' },
  { value: 'sa', label: 'Semiannual' },
  { value: 'a', label: 'Annual' },
]

export const AGGREGATION_OPTIONS: { value: FredAggregation; label: string }[] = [
  { value: 'avg', label: 'Average' },
  { value: 'sum', label: 'Sum' },
  { value: 'eop', label: 'End of period' },
]

const PERCENT_UNITS: readonly Transform[] = ['pch', 'pc1', 'pca', 'cch', 'cca']

/** The Units value of a `?t=` link; the old `level` and `yoy` links read as `lin` and `pc1`. */
export function parseTransform(v: string | null): Transform {
  if (v === 'level') return 'lin'
  if (v === 'yoy') return 'pc1'
  return TRANSFORM_OPTIONS.find((o) => o.value === v)?.value ?? 'lin'
}

/** The FRED units to request: `index` rebases the levels client-side. */
export function serverUnits(t: Transform): FredUnits {
  return t === 'index' ? 'lin' : t
}

/** Units whose values are percentages (shown with a % sign). */
export function isPercentTransform(t: Transform): boolean {
  return PERCENT_UNITS.includes(t)
}

/** Levels (as reported or indexed): period changes of these read as percent changes. */
export function isLevelTransform(t: Transform): boolean {
  return t === 'lin' || t === 'index'
}

/** Extract a single series' sorted numeric points from a bundle-observations payload. */
export function seriesPoints(obs: BundleObservations, seriesId: string): RawPoint[] {
  return obs.observations
    .filter((o) => o.series === seriesId)
    .map((o) => ({ date: o.date, value: Number(o.value) }))
    .filter((p) => Number.isFinite(p.value))
    .sort((a, b) => a.date.localeCompare(b.date))
}

function shiftDays(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function rangeCutoff(range: RangeKey): string | null {
  if (range === 'max') return null
  const d = new Date()
  d.setFullYear(d.getFullYear() - Number(range))
  return d.toISOString().slice(0, 10)
}

export function applyRange(points: RawPoint[], range: RangeKey): RawPoint[] {
  const cut = rangeCutoff(range)
  return cut ? points.filter((p) => p.date >= cut) : points
}

/** Nearest point to `target` date within `tolDays`, searching points[0..hi]. */
function nearest(points: RawPoint[], target: string, hi: number, tolDays = 45): RawPoint | null {
  // binary search for insertion index of target among points[0..hi]
  let lo = 0
  let h = hi
  while (lo < h) {
    const mid = (lo + h) >> 1
    if (points[mid].date < target) lo = mid + 1
    else h = mid
  }
  const candidates = [points[lo - 1], points[lo]].filter(Boolean) as RawPoint[]
  let best: RawPoint | null = null
  let bestDiff = Infinity
  const t = new Date(`${target}T00:00:00`).getTime()
  for (const c of candidates) {
    const diff = Math.abs(new Date(`${c.date}T00:00:00`).getTime() - t)
    if (diff < bestDiff) {
      bestDiff = diff
      best = c
    }
  }
  return best && bestDiff <= tolDays * 86400000 ? best : null
}

/** Chart-ready values: the API's values as they are (it already applied the FRED units), or
 *  for `index` the levels rebased to 100 at the first non-zero value in the window. */
export function applyTransform(points: RawPoint[], t: Transform): ChartPoint[] {
  if (points.length === 0) return []
  if (t === 'index') {
    const base = points.find((p) => p.value !== 0)?.value
    return points.map((p) => ({ x: p.date, y: base ? (p.value / base) * 100 : null }))
  }
  return points.map((p) => ({ x: p.date, y: p.value }))
}

export type Change = { abs: number | null; pct: number | null }

/** Change of the latest value vs the value ~`days` ago (absolute + percent). */
export function changeOver(points: RawPoint[], days: number): Change {
  if (points.length < 2) return { abs: null, pct: null }
  const last = points[points.length - 1]
  const prev = nearest(points, shiftDays(last.date, -days), points.length - 1, days < 60 ? 20 : 50)
  if (!prev) return { abs: null, pct: null }
  return { abs: last.value - prev.value, pct: prev.value !== 0 ? (last.value / prev.value - 1) * 100 : null }
}

export type SeriesStats = {
  latest: number
  latestDate: string
  min: number
  max: number
  chg1m: Change
  chg3m: Change
  chg1y: Change
}

export function seriesStats(points: RawPoint[]): SeriesStats | null {
  if (points.length === 0) return null
  const latest = points[points.length - 1]
  const values = points.map((p) => p.value)
  return {
    latest: latest.value,
    latestDate: latest.date,
    min: Math.min(...values),
    max: Math.max(...values),
    chg1m: changeOver(points, 30),
    chg3m: changeOver(points, 92),
    chg1y: changeOver(points, 365),
  }
}

/** A rate/percent-unit series (show absolute point change, not % change). */
export function isRateUnit(units: string | undefined): boolean {
  const u = (units || '').toLowerCase()
  return u.includes('percent') || u.trim() === '%'
}
