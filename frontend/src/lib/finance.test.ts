import { describe, expect, it } from 'vitest'
import {
  computeRatios,
  formatDerivedMetric,
  periodChange,
  pickLatest,
  withPeriodChange,
} from './finance'
import type { LatestValue, TimeseriesPoint } from './types'

function fact(concept: string, value: number, unit = 'USD'): LatestValue {
  return { concept, value, unit, period_end: '2024-12-31', period_start: '2024-01-01', dimensions: {} }
}

describe('pickLatest', () => {
  it('returns the first concept that has a value', () => {
    const values = { Revenues: fact('Revenues', 100) }
    expect(pickLatest(values, ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues'])?.value).toBe(100)
  })
  it('skips null values', () => {
    const values = { Revenues: fact('Revenues', 0) }
    values.Revenues.value = null
    expect(pickLatest(values, ['Revenues'])).toBeUndefined()
  })
})

describe('computeRatios', () => {
  it('computes margins and debt/equity from picked highlights', () => {
    const ratios = computeRatios({
      revenue: fact('Revenues', 200),
      gross_profit: fact('GrossProfit', 80),
      op_income: fact('OperatingIncomeLoss', 40),
      net_income: fact('NetIncomeLoss', 20),
      liabilities: fact('Liabilities', 150),
      equity: fact('StockholdersEquity', 50),
    })
    expect(ratios.map((r) => r.key)).toEqual(['gross_margin', 'operating_margin', 'net_margin', 'debt_to_equity'])
    expect(ratios[0].display).toBe('40.0%')
    expect(ratios[1].display).toBe('20.0%')
    expect(ratios[2].display).toBe('10.0%')
    expect(ratios[3].display).toBe('3.00x')
  })
  it('omits ratios when revenue is missing or zero', () => {
    expect(computeRatios({ revenue: fact('Revenues', 0), gross_profit: fact('GrossProfit', 10) })).toEqual([])
    expect(computeRatios({ gross_profit: fact('GrossProfit', 10) })).toEqual([])
  })
})

describe('periodChange', () => {
  it('returns signed percent vs the previous period', () => {
    expect(periodChange(110, 100)).toEqual({ pct: 10, direction: 1 })
    expect(periodChange(90, 100)).toEqual({ pct: -10, direction: -1 })
    expect(periodChange(100, 100)).toEqual({ pct: 0, direction: 0 })
  })
  it('is null when previous is missing or zero', () => {
    expect(periodChange(10, null)).toBeNull()
    expect(periodChange(10, 0)).toBeNull()
  })
})

describe('withPeriodChange', () => {
  it('compares each row to the next (older) row', () => {
    const series: TimeseriesPoint[] = [
      { period_end: '2024-12-31', period_start: '2024-01-01', value: 110, unit: 'USD', dimensions: {} },
      { period_end: '2023-12-31', period_start: '2023-01-01', value: 100, unit: 'USD', dimensions: {} },
    ]
    const rows = withPeriodChange(series)
    expect(rows[0].delta).toEqual({ pct: 10, direction: 1 })
    expect(rows[1].delta).toBeNull()
  })
})

describe('formatDerivedMetric', () => {
  it('renders margins as percents and other ratios as multiples', () => {
    expect(formatDerivedMetric('gross_margin', 0.462, 'ratio')).toBe('46.2%')
    expect(formatDerivedMetric('inventory_turns_sales_basis', 8.5, 'ratio')).toBe('8.50x')
    expect(formatDerivedMetric('working_capital_proxy', 1_000_000, 'USD')).toBe('$1.00M')
  })
})
