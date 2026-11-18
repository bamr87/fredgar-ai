import { describe, expect, it } from 'vitest'
import {
  applyTransform,
  changeOver,
  isPercentTransform,
  isRateUnit,
  parseTransform,
  serverUnits,
  seriesStats,
  type RawPoint,
} from './macro'

// Monthly-ish points: value doubles over 12 steps.
const monthly: RawPoint[] = Array.from({ length: 25 }, (_, i) => ({
  date: `20${24 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}-01`,
  value: 100 + i * 10,
}))

describe('applyTransform', () => {
  it('levels pass values through', () => {
    const out = applyTransform(monthly, 'lin')
    expect(out[0].y).toBe(100)
    expect(out[out.length - 1].y).toBe(340)
  })
  it('index rebases to 100 at the window start', () => {
    const out = applyTransform(monthly, 'index')
    expect(out[0].y).toBe(100)
    expect(out[12].y).toBeCloseTo((220 / 100) * 100, 5)
  })
  it('FRED units pass the server-computed values through', () => {
    // The API already applied pc1; the browser must not transform them again.
    const out = applyTransform(monthly, 'pc1')
    expect(out.map((p) => p.y)).toEqual(monthly.map((p) => p.value))
  })
})

describe('the Units control', () => {
  it('reads old level / yoy links as lin / pc1', () => {
    expect(parseTransform('level')).toBe('lin')
    expect(parseTransform('yoy')).toBe('pc1')
  })
  it('keeps a known unit and falls back to lin', () => {
    expect(parseTransform('cca')).toBe('cca')
    expect(parseTransform('index')).toBe('index')
    expect(parseTransform('bogus')).toBe('lin')
    expect(parseTransform(null)).toBe('lin')
  })
  it('asks the API for levels when indexing client-side', () => {
    expect(serverUnits('index')).toBe('lin')
    expect(serverUnits('pc1')).toBe('pc1')
  })
  it('knows which units are percentages', () => {
    expect(isPercentTransform('pc1')).toBe(true)
    expect(isPercentTransform('cca')).toBe(true)
    expect(isPercentTransform('chg')).toBe(false)
    expect(isPercentTransform('log')).toBe(false)
    expect(isPercentTransform('index')).toBe(false)
  })
})

describe('changeOver', () => {
  it('returns absolute and percent change', () => {
    const c = changeOver(monthly, 365)
    expect(c.abs).not.toBeNull()
    expect(c.pct).not.toBeNull()
    expect((c.pct as number) > 0).toBe(true)
  })
})

describe('seriesStats', () => {
  it('reports latest / min / max', () => {
    const s = seriesStats(monthly)!
    expect(s.latest).toBe(340)
    expect(s.min).toBe(100)
    expect(s.max).toBe(340)
  })
  it('handles empty input', () => {
    expect(seriesStats([])).toBeNull()
  })
})

describe('isRateUnit', () => {
  it('detects percent units', () => {
    expect(isRateUnit('Percent')).toBe(true)
    expect(isRateUnit('Billions of Dollars')).toBe(false)
  })
})
