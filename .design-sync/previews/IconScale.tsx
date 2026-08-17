import { Button, Card, IconScale } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconScale width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconScale />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconScale width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconScale width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconScale width={28} height={28} />
    <IconScale width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconScale width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconScale width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconScale width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconScale width={16} height={16} /> Balance sheet
      </Button>
      <Button variant="primary" size="sm">
        <IconScale width={16} height={16} /> Balance sheet
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconScale /> Balance sheet
        </span>
        <span className="nav-item">
          <IconScale /> Balance sheet
        </span>
      </div>
    </Card>
  </div>
)
