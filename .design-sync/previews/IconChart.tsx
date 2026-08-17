import { Button, Card, IconChart } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconChart width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconChart />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconChart width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconChart width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconChart width={28} height={28} />
    <IconChart width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconChart width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconChart width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconChart width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconChart width={16} height={16} /> View chart
      </Button>
      <Button variant="primary" size="sm">
        <IconChart width={16} height={16} /> View chart
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconChart /> Analytics
        </span>
        <span className="nav-item">
          <IconChart /> Analytics
        </span>
      </div>
    </Card>
  </div>
)
