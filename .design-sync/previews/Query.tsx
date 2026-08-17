import { ApiError, Card, CardHeader, Query } from 'frontend'

type Filing = { id: number; form: string; filed: string }

// The component reads only these four fields off a TanStack query result, so a
// plain object is enough to drive each branch in a static preview.
const result = (over: Partial<{ isPending: boolean; isError: boolean; error: unknown; data: unknown }>) =>
  ({ isPending: false, isError: false, error: null, data: undefined, ...over }) as never

const filings: Filing[] = [
  { id: 1, form: '10-K', filed: '2024-11-01' },
  { id: 2, form: '10-Q', filed: '2024-08-02' },
  { id: 3, form: '8-K', filed: '2024-07-15' },
]

const List = (rows: Filing[]) => (
  <div className="col gap-2 card-body">
    {rows.map((f) => (
      <div key={f.id} className="row between">
        <span className="mono">{f.form}</span>
        <span className="muted text-sm">{f.filed}</span>
      </div>
    ))}
  </div>
)

export const Success = () => (
  <Card>
    <CardHeader title="Recent filings" />
    <Query q={result({ data: filings })}>{(data: Filing[]) => List(data)}</Query>
  </Card>
)

export const Pending = () => (
  <Card>
    <CardHeader title="Recent filings" />
    <Query q={result({ isPending: true })} loadingLabel="Loading filings…">
      {(data: Filing[]) => List(data)}
    </Query>
  </Card>
)

export const Empty = () => (
  <Card>
    <CardHeader title="Recent filings" />
    <Query q={result({ data: [] })} isEmpty={(d: Filing[]) => d.length === 0}>
      {(data: Filing[]) => List(data)}
    </Query>
  </Card>
)

export const Failed = () => (
  <Card>
    <CardHeader title="Recent filings" />
    <Query q={result({ isError: true, error: new ApiError(502, 'Upstream SEC request failed.', null) })}>
      {(data: Filing[]) => List(data)}
    </Query>
  </Card>
)
