import { Card, CompanySearch } from 'frontend'

export const Default = () => (
  <Card>
    <div className="card-pad" style={{ maxWidth: 520 }}>
      <CompanySearch />
    </div>
  </Card>
)

export const WithKbdHint = () => (
  <Card>
    <div className="card-pad" style={{ maxWidth: 520 }}>
      <CompanySearch kbd placeholder="Search companies…  (⌘K)" />
    </div>
  </Card>
)

export const InATopBar = () => (
  <Card>
    <div className="topbar" style={{ position: 'static' }}>
      <div className="grow" style={{ maxWidth: 460 }}>
        <CompanySearch kbd />
      </div>
    </div>
  </Card>
)
