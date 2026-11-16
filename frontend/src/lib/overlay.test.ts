import { describe, expect, it } from 'vitest'
import { toCsv } from './csv'
import {
  OVERLAY_CSV_COLUMNS,
  companySeriesOptions,
  correlationSummary,
  droppedReason,
  overlayChartRows,
  overlayCsvRows,
  storedSeries,
} from './overlay'
import type { BundleObservations, MacroOverlay } from './types'

const OVERLAY: MacroOverlay = {
  company: 1,
  company_series: { source: 'concept', key: 'Revenues', concepts: ['Revenues'], taxonomy: 'us-gaap', unit: 'USD', annual: true },
  series: { external_id: 'GDP', provider: 'fred', title: 'Gross Domestic Product', units: 'Billions of Dollars', frequency: 'Quarterly' },
  alignment: { window: 'fiscal', aggregation: 'avg', series_step_days: 91, description: 'fiscal windows', dropped: [] },
  rows: [
    { period_start: '2022-07-01', period_end: '2023-06-30', company_value: 300, series_value: 26000, series_observations: 4 },
    { period_start: '2020-07-01', period_end: '2021-06-30', company_value: 100, series_value: 22000, series_observations: 4 },
    { period_start: '2021-07-01', period_end: '2022-06-30', company_value: 200, series_value: 24000, series_observations: 4 },
  ],
  correlation: { method: 'pearson', r: 1, n: 3 },
}

describe('companySeriesOptions', () => {
  it('lists the reported concept chains, then the distinct derived metrics (annual)', () => {
    const opts = companySeriesOptions([{ key: 'gross_margin' }, { key: 'current_ratio' }, { key: 'gross_margin' }])
    expect(opts[0]).toMatchObject({ value: 'concept:revenue', label: 'Revenue', group: 'Reported (XBRL)', annual: true })
    expect(opts[0].concepts).toContain('Revenues')
    const derived = opts.filter((o) => o.group === 'Derived metrics')
    expect(derived.map((o) => o.metric)).toEqual(['current_ratio', 'gross_margin'])
    expect(derived.every((o) => o.annual && !o.concepts)).toBe(true)
  })
})

describe('storedSeries', () => {
  it('keeps only the series that have stored observations', () => {
    const obs: BundleObservations = {
      bundle: 'core',
      count: 1,
      series: [
        { external_id: 'GDP', title: 'GDP', units: '', frequency: 'Quarterly', note: '', industries: [] },
        { external_id: 'NEVER', title: 'Never synced', units: '', frequency: '', note: '', industries: [] },
      ],
      observations: [{ series: 'GDP', provider: 'fred', date: '2024-01-01', value: '1' }],
    }
    expect(storedSeries(obs).map((s) => s.external_id)).toEqual(['GDP'])
  })
})

describe('overlayChartRows', () => {
  it('sorts by period end and puts the company left, the series right', () => {
    expect(overlayChartRows(OVERLAY)).toEqual([
      { x: '2021-06-30', left: 100, right: 22000 },
      { x: '2022-06-30', left: 200, right: 24000 },
      { x: '2023-06-30', left: 300, right: 26000 },
    ])
  })
})

describe('overlayCsvRows', () => {
  it('exports one row per aligned period with both series and the aggregation', () => {
    const rows = overlayCsvRows(OVERLAY)
    expect(rows[0]).toEqual({
      period_start: '2022-07-01',
      period_end: '2023-06-30',
      company_series: 'Revenues',
      company_value: 300,
      company_unit: 'USD',
      series_id: 'GDP',
      series_value: 26000,
      series_units: 'Billions of Dollars',
      aggregation: 'avg',
      series_observations: 4,
    })
    const csv = toCsv(rows, [...OVERLAY_CSV_COLUMNS])
    expect(csv.split('\n')[0]).toBe(OVERLAY_CSV_COLUMNS.join(','))
    expect(csv.split('\n')).toHaveLength(4)
  })
})

describe('correlationSummary', () => {
  it('labels strength and sign', () => {
    expect(correlationSummary(0.82, 12)).toEqual({ text: 'r = 0.82 · strong positive · n = 12', tone: 'pos' })
    expect(correlationSummary(-0.5, 8)).toEqual({ text: 'r = -0.50 · moderate negative · n = 8', tone: 'neg' })
    expect(correlationSummary(0.25, 8).text).toContain('weak positive')
    expect(correlationSummary(0.05, 8)).toEqual({ text: 'r = 0.05 · no correlation · n = 8', tone: 'default' })
  })
  it('says why r is missing below three periods', () => {
    expect(correlationSummary(null, 2)).toEqual({ text: 'r n/a · n = 2 (needs 3+ aligned periods)', tone: 'default' })
    expect(correlationSummary(null, 5).text).toBe('r n/a · n = 5')
  })
})

describe('droppedReason', () => {
  it('explains known reasons and passes unknown ones through', () => {
    expect(droppedReason('gap')).toBe('a missing observation inside the period')
    expect(droppedReason('something_new')).toBe('something_new')
  })
})
