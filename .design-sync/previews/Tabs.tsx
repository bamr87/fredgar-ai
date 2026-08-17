import { Card, IconChart, IconFile, IconSparkle, IconUsers, Tabs } from 'frontend'

export const CompanyTabs = () => (
  <Card>
    <Tabs
      value="financials"
      onChange={() => {}}
      tabs={[
        { key: 'overview', label: 'Overview' },
        { key: 'financials', label: 'Financials' },
        { key: 'filings', label: 'Filings' },
        { key: 'facts', label: 'Facts' },
        { key: 'leadership', label: 'Leadership' },
      ]}
    />
  </Card>
)

export const WithCounts = () => (
  <Card>
    <Tabs
      value="filings"
      onChange={() => {}}
      tabs={[
        { key: 'filings', label: 'Filings', count: 128 },
        { key: 'documents', label: 'Documents', count: 4210 },
        { key: 'facts', label: 'Facts', count: 612940 },
      ]}
    />
  </Card>
)

export const WithIcons = () => (
  <Card>
    <Tabs
      value="leadership"
      onChange={() => {}}
      tabs={[
        { key: 'financials', label: 'Financials', icon: <IconChart /> },
        { key: 'filings', label: 'Filings', icon: <IconFile />, count: 128 },
        { key: 'leadership', label: 'Leadership', icon: <IconUsers /> },
        { key: 'analysis', label: 'AI analysis', icon: <IconSparkle /> },
      ]}
    />
  </Card>
)
