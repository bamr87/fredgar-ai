import { Badge, Button, Card, CardHeader, IconChart, IconFile } from 'frontend'

export const TitleAndSub = () => (
  <Card>
    <CardHeader title="Cash flow statement" sub="Microsoft Corporation · FY2024 · filed 2024-07-30" />
    <div className="card-body muted">Statement rows render here.</div>
  </Card>
)

export const WithIconAndActions = () => (
  <Card>
    <CardHeader
      icon={<IconChart />}
      title="Revenue trend"
      sub="Trailing 8 fiscal years"
      actions={
        <>
          <Button size="sm" variant="ghost">
            Annual
          </Button>
          <Button size="sm">Export</Button>
        </>
      }
    />
    <div className="card-body muted">Chart renders here.</div>
  </Card>
)

export const TitleOnly = () => (
  <Card>
    <CardHeader
      icon={<IconFile />}
      title={
        <span className="row gap-2">
          Recent filings <Badge tone="info">12</Badge>
        </span>
      }
    />
    <div className="card-body muted">Filing list renders here.</div>
  </Card>
)
