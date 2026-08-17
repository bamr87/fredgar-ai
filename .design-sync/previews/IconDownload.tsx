import { Button, Card, IconDownload } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)', alignItems: 'flex-end' }}>
    <div className="col gap-2 center">
      <IconDownload width={16} height={16} />
      <span className="caption">16</span>
    </div>
    <div className="col gap-2 center">
      <IconDownload />
      <span className="caption">20 (default)</span>
    </div>
    <div className="col gap-2 center">
      <IconDownload width={32} height={32} />
      <span className="caption">32</span>
    </div>
    <div className="col gap-2 center">
      <IconDownload width={48} height={48} />
      <span className="caption">48</span>
    </div>
  </div>
)

export const Tones = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <IconDownload width={28} height={28} />
    <IconDownload width={28} height={28} style={{ color: 'var(--c-text-muted)' }} />
    <IconDownload width={28} height={28} style={{ color: 'var(--c-accent)' }} />
    <IconDownload width={28} height={28} style={{ color: 'var(--c-positive)' }} />
    <IconDownload width={28} height={28} style={{ color: 'var(--c-negative)' }} />
  </div>
)

export const InContext = () => (
  <div className="col gap-3" style={{ padding: 'var(--sp-4)' }}>
    <div className="row gap-3 wrap">
      <Button size="sm">
        <IconDownload width={16} height={16} /> Download CSV
      </Button>
      <Button variant="primary" size="sm">
        <IconDownload width={16} height={16} /> Download CSV
      </Button>
    </div>
    <Card>
      <div className="card-pad col gap-1" style={{ maxWidth: 232 }}>
        <span className="nav-item active">
          <IconDownload /> Exports
        </span>
        <span className="nav-item">
          <IconDownload /> Exports
        </span>
      </div>
    </Card>
  </div>
)
