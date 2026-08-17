import { Button, Card, IconGroup } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconGroup width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconGroup />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconGroup width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconGroup width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconGroup width={28} height={28} />
    <IconGroup width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconGroup width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconGroup width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconGroup width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconGroup width={16} height={16} /> New peer group
      </Button>
      <Button variant="primary" size="sm">
        <IconGroup width={16} height={16} /> New peer group
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconGroup /> Peer groups
        </span>
        <span className="nav-item">
          <IconGroup /> Peer groups
        </span>
      </div>
    </Card>
  </div>
)
