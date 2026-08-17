import { Button, Card, IconLayers } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconLayers width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconLayers />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconLayers width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconLayers width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconLayers width={28} height={28} />
    <IconLayers width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconLayers width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconLayers width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconLayers width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconLayers width={16} height={16} /> Browse facts
      </Button>
      <Button variant="primary" size="sm">
        <IconLayers width={16} height={16} /> Browse facts
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconLayers /> Datasets
        </span>
        <span className="nav-item">
          <IconLayers /> Datasets
        </span>
      </div>
    </Card>
  </div>
)
