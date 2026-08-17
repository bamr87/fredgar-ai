import { Card, Provenance, Stat } from 'frontend'

export const SourceAndDate = () => (
  <div className="col gap-3">
    <Provenance source="SEC EDGAR companyfacts" asOf="2025-02-07T00:00:00Z" />
    <Provenance source="FRED series GDPC1" asOf="2025-01-30T00:00:00Z" />
    <Provenance source="Derived metric — computed" />
  </div>
)

export const OnAStat = () => (
  <div className="grid grid-2">
    <Card>
      <div className="stat">
        <div className="stat-label">Revenue (FY2024)</div>
        <div className="stat-value">$391.0B</div>
        <Provenance source="SEC EDGAR us-gaap:Revenues" asOf="2024-11-01T00:00:00Z" />
      </div>
    </Card>
    <Card>
      <div className="stat">
        <div className="stat-label">Real GDP</div>
        <div className="stat-value">$23.5T</div>
        <Provenance source="FRED GDPC1" asOf="2025-01-30T00:00:00Z" />
      </div>
    </Card>
  </div>
)

export const InlineWithMetric = () => (
  <div className="col gap-2">
    <Stat label="Free cash flow" value="$108.8B" sub={<Provenance source="Derived from us-gaap cash flow facts" asOf="2024-11-01T00:00:00Z" />} />
  </div>
)
