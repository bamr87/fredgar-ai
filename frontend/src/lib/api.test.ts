import { describe, expect, it } from 'vitest'
import { bundleObservationsPath, seriesTransformQuery } from './api'

describe('seriesTransformQuery', () => {
  it('sends nothing for the defaults, so an untransformed request is unchanged', () => {
    expect(seriesTransformQuery()).toEqual({ units: undefined, frequency: undefined, aggregation: undefined, vintage_date: undefined })
    expect(seriesTransformQuery({ units: 'lin', frequency: '', aggregation: 'avg' })).toEqual(seriesTransformQuery())
  })
  it('sends FRED units and frequency', () => {
    expect(seriesTransformQuery({ units: 'pc1', frequency: 'q' })).toMatchObject({ units: 'pc1', frequency: 'q', aggregation: undefined })
  })
  it('sends a non-default aggregation only with a frequency', () => {
    expect(seriesTransformQuery({ frequency: 'a', aggregation: 'eop' }).aggregation).toBe('eop')
    expect(seriesTransformQuery({ aggregation: 'sum' }).aggregation).toBeUndefined()
  })
  it('passes a vintage date through', () => {
    expect(seriesTransformQuery({ vintageDate: '2020-01-01' }).vintage_date).toBe('2020-01-01')
  })
})

describe('bundleObservationsPath', () => {
  it('is the plain observations URL without a transform', () => {
    expect(bundleObservationsPath('core')).toBe('/api/v1/series-bundles/core/observations/?per_series=2000')
  })
  it('appends the FRED params', () => {
    expect(bundleObservationsPath('core', 2000, { units: 'pc1', frequency: 'q', aggregation: 'sum' })).toBe(
      '/api/v1/series-bundles/core/observations/?per_series=2000&units=pc1&frequency=q&aggregation=sum',
    )
  })
})
