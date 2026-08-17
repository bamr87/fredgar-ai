import { Badge, Button, Card, CardHeader } from 'frontend'

export const WithHeader = () => (
  <Card>
    <CardHeader
      title="Income statement"
      sub="Apple Inc. · FY2024 · 10-K filed 2024-11-01"
      actions={<Button size="sm">Export CSV</Button>}
    />
    <div className="card-body col gap-3">
      <div className="row between">
        <span className="muted">Total revenue</span>
        <span className="num">$391,035M</span>
      </div>
      <div className="row between">
        <span className="muted">Gross profit</span>
        <span className="num">$180,683M</span>
      </div>
      <div className="row between">
        <span className="muted">Operating income</span>
        <span className="num">$123,216M</span>
      </div>
    </div>
  </Card>
)

export const Padded = () => (
  <Card>
    <div className="card-pad col gap-2">
      <div className="row gap-2">
        <h3>Peer group: Mega-cap technology</h3>
        <Badge tone="accent">8 members</Badge>
      </div>
      <p className="muted">
        Cohort assembled from SIC 3571 and 7372 issuers with market capitalisation above $500B.
      </p>
    </div>
  </Card>
)

export const Hoverable = () => (
  <div className="grid grid-2">
    <Card hover>
      <div className="card-pad col gap-1">
        <div className="row gap-2">
          <span className="mono">AAPL</span>
          <Badge tone="pos">Synced</Badge>
        </div>
        <div className="muted text-sm">Apple Inc. · CIK 0000320193</div>
      </div>
    </Card>
    <Card hover>
      <div className="card-pad col gap-1">
        <div className="row gap-2">
          <span className="mono">NVDA</span>
          <Badge tone="warn">Stale</Badge>
        </div>
        <div className="muted text-sm">NVIDIA Corporation · CIK 0001045810</div>
      </div>
    </Card>
  </div>
)
