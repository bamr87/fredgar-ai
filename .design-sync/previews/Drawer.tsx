import { Badge, Button, Drawer, Provenance } from 'frontend'

export const FilingDetail = () => (
  <Drawer
    open
    onClose={() => {}}
    title="10-K — Apple Inc."
    sub="Accession 0000320193-24-000123 · filed 2024-11-01"
  >
    <div className="col gap-4">
      <div className="row gap-2 wrap">
        <Badge tone="accent">10-K</Badge>
        <Badge tone="info">FY2024</Badge>
        <Badge tone="pos" dot>
          Documents ingested
        </Badge>
      </div>
      <div className="col gap-2">
        <span className="field-label">Period of report</span>
        <span className="mono">2024-09-28</span>
      </div>
      <div className="col gap-2">
        <span className="field-label">Primary document</span>
        <span className="mono">aapl-20240928.htm</span>
      </div>
      <hr className="divider" />
      <p className="muted">
        The annual report contains audited financial statements, risk factors, and management's
        discussion and analysis for the fiscal year.
      </p>
      <div className="row gap-2">
        <Button variant="primary">Open on EDGAR</Button>
        <Button>Download</Button>
      </div>
      <Provenance source="SEC EDGAR submissions" asOf="2024-11-01T00:00:00Z" />
    </div>
  </Drawer>
)
