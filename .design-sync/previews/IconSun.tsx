import { Button, Card, IconSun } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconSun width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconSun />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconSun width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconSun width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconSun width={28} height={28} />
    <IconSun width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconSun width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconSun width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconSun width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconSun width={16} height={16} /> Light theme
      </Button>
      <Button variant="primary" size="sm">
        <IconSun width={16} height={16} /> Light theme
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconSun /> Appearance
        </span>
        <span className="nav-item">
          <IconSun /> Appearance
        </span>
      </div>
    </Card>
  </div>
)
