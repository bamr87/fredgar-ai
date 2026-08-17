import { Card, CompanyMultiSelect } from 'frontend'

const cohort = [
  { id: 1, name: 'Apple Inc.', ticker: 'AAPL', cik: '0000320193' },
  { id: 2, name: 'Microsoft Corporation', ticker: 'MSFT', cik: '0000789019' },
  { id: 3, name: 'NVIDIA Corporation', ticker: 'NVDA', cik: '0001045810' },
]

export const WithSelection = () => (
  <Card>
    <div className="card-pad" style={{ maxWidth: 560 }}>
      <CompanyMultiSelect selected={cohort} onChange={() => {}} />
    </div>
  </Card>
)

export const Empty = () => (
  <Card>
    <div className="card-pad" style={{ maxWidth: 560 }}>
      <CompanyMultiSelect selected={[]} onChange={() => {}} placeholder="Add a company to the cohort…" />
    </div>
  </Card>
)

export const SingleChip = () => (
  <Card>
    <div className="card-pad" style={{ maxWidth: 560 }}>
      <CompanyMultiSelect selected={cohort.slice(0, 1)} onChange={() => {}} />
    </div>
  </Card>
)
