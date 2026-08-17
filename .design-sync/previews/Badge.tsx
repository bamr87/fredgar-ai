import { Badge } from 'frontend'

export const Tones = () => (
  <div className="row gap-2 wrap">
    <Badge>10-K</Badge>
    <Badge tone="accent">Large accelerated filer</Badge>
    <Badge tone="pos">Synced</Badge>
    <Badge tone="neg">Sync failed</Badge>
    <Badge tone="warn">Stale data</Badge>
    <Badge tone="info">XBRL</Badge>
  </div>
)

export const WithDot = () => (
  <div className="row gap-2 wrap">
    <Badge tone="pos" dot>
      API online
    </Badge>
    <Badge tone="warn" dot>
      Rate limited
    </Badge>
    <Badge tone="neg" dot>
      Offline
    </Badge>
  </div>
)

export const InContext = () => (
  <div className="row gap-2 wrap">
    <span className="mono">AAPL</span>
    <Badge tone="accent">SIC 3571</Badge>
    <Badge tone="info">FY2024</Badge>
    <Badge tone="pos" dot>
      1,284 facts
    </Badge>
  </div>
)
