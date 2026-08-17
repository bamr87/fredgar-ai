import { Card, CardHeader, SkeletonRows } from 'frontend'

export const Default = () => (
  <Card>
    <SkeletonRows />
  </Card>
)

export const InAPanel = () => (
  <Card>
    <CardHeader title="Leadership" sub="Loading officers and directors…" />
    <SkeletonRows rows={5} />
  </Card>
)

export const TallRows = () => (
  <Card>
    <SkeletonRows rows={3} height={28} />
  </Card>
)
