import { Button } from 'frontend'

export const Variants = () => (
  <div className="row gap-3 wrap">
    <Button>Export CSV</Button>
    <Button variant="primary">Sync filings</Button>
    <Button variant="ghost">Cancel</Button>
    <Button variant="danger">Delete peer group</Button>
  </div>
)

export const Sizes = () => (
  <div className="row gap-3 wrap">
    <Button variant="primary">Run comparison</Button>
    <Button variant="primary" size="sm">
      Run comparison
    </Button>
  </div>
)

export const States = () => (
  <div className="row gap-3 wrap">
    <Button variant="primary" loading>
      Syncing submissions…
    </Button>
    <Button disabled>Unavailable</Button>
    <Button variant="ghost" disabled>
      Requires admin token
    </Button>
  </div>
)
