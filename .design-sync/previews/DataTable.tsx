import { Badge, DataTable } from 'frontend'

type Row = { cik: string; ticker: string; name: string; revenue: number; margin: number; filed: string }

const rows: Row[] = [
  { cik: '0000320193', ticker: 'AAPL', name: 'Apple Inc.', revenue: 391035, margin: 46.2, filed: '2024-11-01' },
  { cik: '0000789019', ticker: 'MSFT', name: 'Microsoft Corporation', revenue: 245122, margin: 69.8, filed: '2024-07-30' },
  { cik: '0001018724', ticker: 'AMZN', name: 'Amazon.com, Inc.', revenue: 637959, margin: 48.8, filed: '2025-02-07' },
  { cik: '0001652044', ticker: 'GOOGL', name: 'Alphabet Inc.', revenue: 350018, margin: 58.2, filed: '2025-02-05' },
  { cik: '0001045810', ticker: 'NVDA', name: 'NVIDIA Corporation', revenue: 130497, margin: 75.0, filed: '2025-02-26' },
]

const usd = (n: number) => `$${(n / 1000).toFixed(1)}B`

const columns = [
  {
    key: 'ticker',
    header: 'Ticker',
    render: (r: Row) => <span className="mono">{r.ticker}</span>,
    sortable: true,
    sortValue: (r: Row) => r.ticker,
    width: 90,
  },
  { key: 'name', header: 'Company', render: (r: Row) => r.name, sortable: true, sortValue: (r: Row) => r.name },
  {
    key: 'revenue',
    header: 'Revenue',
    align: 'right' as const,
    render: (r: Row) => usd(r.revenue),
    sortable: true,
    sortValue: (r: Row) => r.revenue,
  },
  {
    key: 'margin',
    header: 'Gross margin',
    align: 'right' as const,
    render: (r: Row) => <Badge tone={r.margin >= 60 ? 'pos' : 'default'}>{r.margin.toFixed(1)}%</Badge>,
    sortable: true,
    sortValue: (r: Row) => r.margin,
  },
  { key: 'filed', header: 'Last 10-K', align: 'right' as const, render: (r: Row) => r.filed, sortable: true, sortValue: (r: Row) => r.filed },
]

export const Sortable = () => (
  <div className="card">
    <DataTable columns={columns} rows={rows} rowKey={(r: Row) => r.cik} initialSort={{ key: 'revenue', dir: 'desc' }} />
  </div>
)

export const Compact = () => (
  <div className="card">
    <DataTable columns={columns.slice(0, 4)} rows={rows.slice(0, 4)} rowKey={(r: Row) => r.cik} compact />
  </div>
)

export const Clickable = () => (
  <div className="card">
    <DataTable
      columns={columns.slice(0, 3)}
      rows={rows.slice(0, 3)}
      rowKey={(r: Row) => r.cik}
      onRowClick={() => {}}
    />
  </div>
)
