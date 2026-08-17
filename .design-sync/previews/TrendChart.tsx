import { Card, CardHeader, TrendChart } from 'frontend'

const revenue = [
  { x: 'FY2017', y: 229234 },
  { x: 'FY2018', y: 265595 },
  { x: 'FY2019', y: 260174 },
  { x: 'FY2020', y: 274515 },
  { x: 'FY2021', y: 365817 },
  { x: 'FY2022', y: 394328 },
  { x: 'FY2023', y: 383285 },
  { x: 'FY2024', y: 391035 },
]

export const AreaChart = () => (
  <Card>
    <CardHeader title="Total revenue" sub="Apple Inc. · annual · US$ millions" />
    <div className="card-body">
      <TrendChart data={revenue} />
    </div>
  </Card>
)

export const LineOnly = () => (
  <Card>
    <CardHeader title="Total revenue" sub="Line variant" />
    <div className="card-body">
      <TrendChart data={revenue} area={false} height={200} />
    </div>
  </Card>
)

export const Colored = () => (
  <Card>
    <CardHeader title="Free cash flow" sub="Positive-tone series" />
    <div className="card-body">
      <TrendChart
        data={[
          { x: 'FY2020', y: 73365 },
          { x: 'FY2021', y: 92953 },
          { x: 'FY2022', y: 111443 },
          { x: 'FY2023', y: 99584 },
          { x: 'FY2024', y: 108807 },
        ]}
        color="var(--c-positive)"
        height={200}
      />
    </div>
  </Card>
)
