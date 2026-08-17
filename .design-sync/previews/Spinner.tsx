import { Spinner } from 'frontend'

export const Sizes = () => (
  <div className="row gap-5" style={{ padding: 'var(--sp-4)' }}>
    <div className="col gap-2 center">
      <Spinner />
      <span className="caption">default (18px)</span>
    </div>
    <div className="col gap-2 center">
      <Spinner lg />
      <span className="caption">lg (30px)</span>
    </div>
  </div>
)

export const Inline = () => (
  <div className="row gap-2" style={{ padding: 'var(--sp-4)' }}>
    <Spinner />
    <span className="muted">Fetching companyfacts from SEC EDGAR…</span>
  </div>
)
