import { Card, ErrorBoundary } from 'frontend'

function Boom(): never {
  throw new Error('Cannot read properties of undefined (reading "statements")')
}

export const CaughtError = () => (
  <ErrorBoundary>
    <Boom />
  </ErrorBoundary>
)

export const PassesChildrenThrough = () => (
  <ErrorBoundary>
    <Card>
      <div className="card-pad col gap-2">
        <h3>Financials</h3>
        <p className="muted">
          When nothing throws, the boundary is invisible and simply renders its children.
        </p>
      </div>
    </Card>
  </ErrorBoundary>
)
