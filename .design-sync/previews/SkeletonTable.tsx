import { Card, CardHeader, SkeletonTable } from 'frontend'

export const Default = () => (
  <Card>
    <SkeletonTable />
  </Card>
)

export const ShortTable = () => (
  <Card>
    <CardHeader title="Recent filings" />
    <SkeletonTable rows={4} />
  </Card>
)
