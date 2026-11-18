import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MacroOverlay } from '../../lib/types'
import { MacroOverlayTab } from './MacroOverlayTab'

const api = vi.hoisted(() => ({
  getCompany: vi.fn(),
  listDerivedMetrics: vi.fn(),
  listSeriesBundles: vi.fn(),
  getBundleObservations: vi.fn(),
  getMacroOverlay: vi.fn(),
  // queries.ts keys bundle observations by this (merged from main with #151)
  seriesTransformQuery: vi.fn(() => ({})),
}))
vi.mock('../../lib/api', () => api)

const csv = vi.hoisted(() => ({ downloadCsv: vi.fn() }))
vi.mock('../../lib/csv', () => csv)

const OVERLAY: MacroOverlay = {
  company: 7,
  company_series: { source: 'concept', key: 'RevenueFromContractWithCustomerExcludingAssessedTax', concepts: ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues'], taxonomy: 'us-gaap', unit: 'USD', annual: true },
  series: { external_id: 'GDP', provider: 'fred', title: 'Gross Domestic Product', units: 'Billions of Dollars', frequency: 'Quarterly' },
  alignment: { window: 'fiscal', aggregation: 'avg', series_step_days: 91, description: 'Each company value covers its fiscal window.', dropped: [] },
  rows: [
    { period_start: '2021-01-01', period_end: '2021-12-31', company_value: 100, series_value: 22000, series_observations: 4 },
    { period_start: '2022-01-01', period_end: '2022-12-31', company_value: 200, series_value: 24000, series_observations: 4 },
    { period_start: '2023-01-01', period_end: '2023-12-31', company_value: 300, series_value: 26000, series_observations: 4 },
  ],
  correlation: { method: 'pearson', r: 0.91, n: 3 },
}

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MacroOverlayTab id={7} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getCompany.mockResolvedValue({ id: 7, name: 'Overlay Corp', ticker: 'OVLY', cik: '0000000007' })
  api.listDerivedMetrics.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, key: 'gross_margin' }] })
  api.listSeriesBundles.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, slug: 'core', name: 'Core', description: '' }] })
  api.getBundleObservations.mockResolvedValue({
    bundle: 'core',
    count: 1,
    series: [
      { external_id: 'GDP', title: 'Gross Domestic Product', units: 'Billions of Dollars', frequency: 'Quarterly', note: '', industries: [] },
      { external_id: 'NEVER', title: 'Never synced', units: '', frequency: '', note: '', industries: [] },
    ],
    observations: [{ series: 'GDP', provider: 'fred', date: '2024-01-01', value: '1' }],
  })
  api.getMacroOverlay.mockResolvedValue(OVERLAY)
})

describe('MacroOverlayTab', () => {
  it('requests the overlay for the first stored series and shows the correlation and table', async () => {
    renderTab()
    expect(await screen.findByText('r = 0.91 · strong positive · n = 3')).toBeInTheDocument()
    expect(api.getMacroOverlay).toHaveBeenCalledWith(7, expect.objectContaining({ series: 'GDP', agg: 'avg', annual: true }))
    expect(api.getMacroOverlay.mock.calls[0][1].concepts).toContain('Revenues')
    // Only the stored series is offered.
    const picker = screen.getByLabelText('Macro series') as HTMLSelectElement
    expect([...picker.options].map((o) => o.value)).toEqual(['GDP'])
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3 periods
  })

  it('switches to a derived metric and to end-of-period aggregation', async () => {
    renderTab()
    await screen.findByText(/strong positive/)
    fireEvent.change(screen.getByLabelText('Company series'), { target: { value: 'metric:gross_margin' } })
    await waitFor(() => expect(api.getMacroOverlay).toHaveBeenLastCalledWith(7, expect.objectContaining({ metric: 'gross_margin', concepts: undefined })))
    fireEvent.click(screen.getByRole('tab', { name: 'End of period' }))
    await waitFor(() => expect(api.getMacroOverlay).toHaveBeenLastCalledWith(7, expect.objectContaining({ agg: 'eop' })))
  })

  it('exports the aligned rows as CSV', async () => {
    renderTab()
    await screen.findByText(/strong positive/)
    fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
    expect(csv.downloadCsv).toHaveBeenCalledTimes(1)
    const [filename, rows, columns] = csv.downloadCsv.mock.calls[0]
    expect(filename).toBe('OVLY-RevenueFromContractWithCustomerExcludingAssessedTax-vs-GDP.csv')
    expect(rows).toHaveLength(3)
    expect(columns).toContain('series_value')
  })

  it('explains why no period aligned', async () => {
    api.getMacroOverlay.mockResolvedValue({
      ...OVERLAY,
      rows: [],
      correlation: { method: 'pearson', r: null, n: 0 },
      alignment: { ...OVERLAY.alignment, dropped: [{ period_start: '2024-01-01', period_end: '2024-12-31', reason: 'series_ends_early' }] },
    })
    renderTab()
    expect(await screen.findByText('No aligned periods')).toBeInTheDocument()
    expect(screen.getByText(/the series ends before the period ends/)).toBeInTheDocument()
  })

  it('says how to store series when there are none, without requesting an overlay', async () => {
    api.listSeriesBundles.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    renderTab()
    expect(await screen.findByText('No macro series stored')).toBeInTheDocument()
    expect(api.getMacroOverlay).not.toHaveBeenCalled()
  })
})
