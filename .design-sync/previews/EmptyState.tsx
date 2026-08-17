import { Button, Card, EmptyState, IconFile, IconGroup } from 'frontend'

export const WithAction = () => (
  <Card>
    <EmptyState
      icon={<IconFile className="state-ico" />}
      title="No filings ingested yet"
      message="This company has no filings in the warehouse. Sync its submissions from SEC EDGAR to populate filings, documents, and XBRL facts."
      action={<Button variant="primary">Sync submissions</Button>}
    />
  </Card>
)

export const MessageOnly = () => (
  <Card>
    <EmptyState
      icon={<IconGroup className="state-ico" />}
      title="No peer groups"
      message="Peer groups let you compare a company against a saved cohort."
    />
  </Card>
)

export const TitleOnly = () => (
  <Card>
    <EmptyState title="No results for “tesle”" />
  </Card>
)
