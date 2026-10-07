import { describe, expect, it } from 'vitest'
import {
  byUnit,
  cik10,
  cikInt,
  compact,
  fullPrecision,
  humanize,
  measureLabel,
  money,
  pct,
  signed,
  signedPctPoints,
} from './format'

describe('compact', () => {
  it('compacts large numbers', () => {
    expect(compact(1_230_000_000)).toBe('1.23B')
    expect(compact(45_600_000)).toBe('45.60M')
    expect(compact(12_300)).toBe('12.3K')
    expect(compact(950)).toBe('950')
  })
  it('handles null / negatives', () => {
    expect(compact(null)).toBe('—')
    expect(compact(-2_000_000)).toBe('-2.00M')
  })
})

describe('money', () => {
  it('prefixes a dollar sign', () => {
    expect(money(1_000_000)).toBe('$1.00M')
  })
})

describe('pct', () => {
  it('formats a ratio as a percentage', () => {
    expect(pct(0.425)).toBe('42.5%')
    expect(pct(null)).toBe('—')
  })
})

describe('byUnit', () => {
  it('respects the unit hint', () => {
    expect(byUnit(0.4, 'ratio')).toBe('0.40')
    expect(byUnit(0.4, 'pct')).toBe('40.0%')
    expect(byUnit(1_000_000, 'USD')).toBe('$1.00M')
    expect(byUnit(6.42, 'USD/shares')).toBe('$6.42')
    expect(byUnit(1500, 'USD/shares')).toBe('$1500.00')
  })
})

describe('fullPrecision', () => {
  it('shows uncompacted currency', () => {
    const usd = fullPrecision(391_035_000_000, 'USD')
    expect(usd).toMatch(/391/)
    expect(usd).not.toMatch(/[TBMK]/)
    expect(fullPrecision(6.42, 'USD/shares')).toMatch(/6\.42/)
  })
})

describe('measureLabel', () => {
  it('normalizes unit tags', () => {
    expect(measureLabel('usd/shares')).toBe('USD/share')
    expect(measureLabel('USD')).toBe('USD')
    expect(measureLabel('ratio')).toBe('')
  })
})

describe('signedPctPoints', () => {
  it('prefixes a sign on percent-point values', () => {
    expect(signedPctPoints(2)).toBe('+2.0%')
    expect(signedPctPoints(-1.4)).toBe('-1.4%')
    expect(signedPctPoints(null)).toBe('—')
  })
})

describe('signed', () => {
  it('adds a sign prefix', () => {
    expect(signed(700)).toBe('+700')
    expect(signed(-700)).toBe('-700')
    expect(signed(0)).toBe('0')
  })
})

describe('cik helpers', () => {
  it('pads and strips CIKs', () => {
    expect(cik10('1318605')).toBe('0001318605')
    expect(cikInt('0001318605')).toBe('1318605')
  })
})

describe('humanize', () => {
  it('turns keys into titles', () => {
    expect(humanize('gross_margin')).toBe('Gross Margin')
    expect(humanize('returnOnEquity')).toBe('Return On Equity')
  })
})
