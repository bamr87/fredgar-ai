import { Button, Card, IconBuilding } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconBuilding width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconBuilding />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconBuilding width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconBuilding width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconBuilding width={28} height={28} />
    <IconBuilding width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconBuilding width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconBuilding width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconBuilding width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconBuilding width={16} height={16} /> Open company
      </Button>
      <Button variant="primary" size="sm">
        <IconBuilding width={16} height={16} /> Open company
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconBuilding /> Companies
        </span>
        <span className="nav-item">
          <IconBuilding /> Companies
        </span>
      </div>
    </Card>
  </div>
)
