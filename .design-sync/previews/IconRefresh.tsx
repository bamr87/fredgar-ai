import { Button, Card, IconRefresh } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconRefresh width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconRefresh />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconRefresh width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconRefresh width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconRefresh width={28} height={28} />
    <IconRefresh width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconRefresh width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconRefresh width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconRefresh width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconRefresh width={16} height={16} /> Sync now
      </Button>
      <Button variant="primary" size="sm">
        <IconRefresh width={16} height={16} /> Sync now
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconRefresh /> Re-sync
        </span>
        <span className="nav-item">
          <IconRefresh /> Re-sync
        </span>
      </div>
    </Card>
  </div>
)
