import { Card, Loading } from 'frontend'

export const Default = () => (
  <Card>
    <Loading />
  </Card>
)

export const CustomLabel = () => (
  <Card>
    <Loading label="Syncing submissions from SEC EDGAR…" />
  </Card>
)

export const InAPanel = () => (
  <Card>
    <div className="card-head">
      <div className="card-title-row">
        <h3>Financial statements</h3>
      </div>
    </div>
    <Loading label="Building income statement…" />
  </Card>
)
