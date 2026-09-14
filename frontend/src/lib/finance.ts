/** Client-side finance helpers: KPI catalog, derived ratios, period-over-period change. */
import { byUnit, num, pct } from './format'
import type { LatestValue, TimeseriesPoint } from './types'

export type ConceptSpec = {
  key: string
  label: string
  concepts: string[]
  annual: boolean
}

export const HIGHLIGHT_KPIS: ConceptSpec[] = [
  {
    key: 'revenue',
    label: 'Revenue',
    concepts: [
      'RevenueFromContractWithCustomerExcludingAssessedTax',
      'Revenues',
      'SalesRevenueNet',
      'RevenueFromContractWithCustomerIncludingAssessedTax',
    ],
    annual: true,
  },
  { key: 'gross_profit', label: 'Gross profit', concepts: ['GrossProfit'], annual: true },
  { key: 'op_income', label: 'Operating income', concepts: ['OperatingIncomeLoss'], annual: true },
  { key: 'net_income', label: 'Net income', concepts: ['NetIncomeLoss'], annual: true },
  { key: 'eps', label: 'EPS (basic)', concepts: ['EarningsPerShareBasic'], annual: true },
  {
    key: 'ocf',
    label: 'Operating cash flow',
    concepts: ['NetCashProvidedByUsedInOperatingActivities'],
    annual: true,
  },
  { key: 'cash', label: 'Cash & equivalents', concepts: ['CashAndCashEquivalentsAtCarryingValue'], annual: false },
  { key: 'assets', label: 'Total assets', concepts: ['Assets'], annual: false },
  { key: 'liabilities', label: 'Total liabilities', concepts: ['Liabilities'], annual: false },
  { key: 'equity', label: "Stockholders' equity", concepts: ['StockholdersEquity'], annual: false },
]

export const TREND_CONCEPTS: ConceptSpec[] = [
  ...HIGHLIGHT_KPIS.filter((k) =>
    ['revenue', 'gross_profit', 'op_income', 'net_income', 'eps', 'ocf', 'assets', 'equity', 'cash'].includes(k.key),
  ),
  { key: 'rnd', label: 'R&D expense', concepts: ['ResearchAndDevelopmentExpense'], annual: true },
]

export const HIGHLIGHT_CONCEPTS: string[] = [...new Set(HIGHLIGHT_KPIS.flatMap((k) => k.concepts))]

export function pickLatest(
  values: Record<string, LatestValue>,
  concepts: string[],
): LatestValue | undefined {
  for (const concept of concepts) {
    const row = values[concept]
    if (row && row.value != null) return row
  }
  return undefined
}

export function pickHighlights(values: Record<string, LatestValue>): Record<string, LatestValue | undefined> {
  return Object.fromEntries(HIGHLIGHT_KPIS.map((k) => [k.key, pickLatest(values, k.concepts)]))
}

export type DerivedRatio = {
  key: string
  label: string
  value: number
  display: string
  signed: boolean
}

export function computeRatios(picked: Record<string, LatestValue | undefined>): DerivedRatio[] {
  const v = (key: string) => num(picked[key]?.value)
  const rev = v('revenue')
  const gross = v('gross_profit')
  const op = v('op_income')
  const net = v('net_income')
  const liab = v('liabilities')
  const eq = v('equity')
  const out: DerivedRatio[] = []
  const addPct = (key: string, label: string, numr: number | null) => {
    if (rev == null || rev === 0 || numr == null) return
    const value = numr / rev
    out.push({ key, label, value, display: pct(value), signed: true })
  }
  addPct('gross_margin', 'Gross margin', gross)
  addPct('operating_margin', 'Operating margin', op)
  addPct('net_margin', 'Net margin', net)
  if (eq != null && eq !== 0 && liab != null) {
    const value = liab / eq
    out.push({ key: 'debt_to_equity', label: 'Debt / equity', value, display: `${value.toFixed(2)}x`, signed: false })
  }
  return out
}

export type PeriodDelta = {
  pct: number
  direction: 1 | -1 | 0
}

export function periodChange(
  current: number | null | undefined,
  previous: number | null | undefined,
): PeriodDelta | null {
  const c = num(current)
  const p = num(previous)
  if (c === null || p === null || p === 0) return null
  const pctPts = ((c - p) / Math.abs(p)) * 100
  const direction: 1 | -1 | 0 = pctPts > 0 ? 1 : pctPts < 0 ? -1 : 0
  return { pct: pctPts, direction }
}

export function withPeriodChange<T extends TimeseriesPoint>(series: T[]): (T & { delta: PeriodDelta | null })[] {
  return series.map((point, i) => ({
    ...point,
    delta: periodChange(point.value, series[i + 1]?.value),
  }))
}

export function toneClass(direction: 1 | -1 | 0 | null | undefined): string {
  if (direction === 1) return 'pos'
  if (direction === -1) return 'neg'
  return ''
}

export function formatDerivedMetric(key: string, value: number | string | null | undefined, unit: string | null): string {
  const n = num(value)
  if (n === null) return '—'
  if (key.includes('margin') || key.includes('intensity')) return pct(n)
  if ((unit || '').toLowerCase() === 'ratio') return `${n.toFixed(2)}x`
  return byUnit(n, unit)
}
