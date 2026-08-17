import { ApiError, Button, Card, ErrorState } from 'frontend'

export const NotFound = () => (
  <Card>
    <ErrorState error={new ApiError(404, 'No company matches CIK 0000000000.', null)} />
  </Card>
)

export const NeedsAdminToken = () => (
  <Card>
    <ErrorState
      error={new ApiError(403, 'Authentication credentials were not provided.', null)}
      action={<Button variant="primary">Open settings</Button>}
    />
  </Card>
)

export const RateLimited = () => (
  <Card>
    <ErrorState
      error={new ApiError(429, 'SEC EDGAR rate limit reached — retry in a few seconds.', null)}
      action={<Button variant="primary">Try again</Button>}
    />
  </Card>
)

export const PlainError = () => (
  <Card>
    <ErrorState error={new Error('Network request failed.')} />
  </Card>
)
