import { Badge, Button, IconDownload, IconRefresh, PageHeader } from 'frontend'

export const WithActionsAndBadges = () => (
  <PageHeader
    title="Apple Inc."
    badges={
      <>
        <Badge tone="accent">AAPL</Badge>
        <Badge tone="info">CIK 0000320193</Badge>
        <Badge tone="pos" dot>
          Synced
        </Badge>
      </>
    }
    desc="Consumer electronics issuer. Financials, filings, documents, and XBRL facts consolidated from SEC EDGAR with full provenance."
    actions={
      <>
        <Button size="sm">
          <IconDownload /> Export
        </Button>
        <Button size="sm" variant="primary">
          <IconRefresh /> Sync
        </Button>
      </>
    }
  />
)

export const TitleAndDescription = () => (
  <PageHeader
    title="Macro workspace"
    desc="FRED economic series grouped into bundles. Overlay indicators against company fundamentals."
  />
)

export const TitleOnly = () => <PageHeader title="Settings" />
