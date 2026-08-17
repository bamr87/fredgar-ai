import { Card, CardHeader, MultiLineChart } from 'frontend'

const years = ['FY2020', 'FY2021', 'FY2022', 'FY2023', 'FY2024']
const pts = (vals: number[]) => years.map((x, i) => ({ x, y: vals[i] }))

export const PeerRevenue = () => (
  <Card>
    <CardHeader title="Revenue — peer overlay" sub="US$ millions · annual" />
    <div className="card-body">
      <MultiLineChart
        height={300}
        series={[
          { id: 'aapl', name: 'Apple', color: 'var(--viz-1)', points: pts([274515, 365817, 394328, 383285, 391035]) },
          { id: 'msft', name: 'Microsoft', color: 'var(--viz-2)', points: pts([143015, 168088, 198270, 211915, 245122]) },
          { id: 'googl', name: 'Alphabet', color: 'var(--viz-3)', points: pts([182527, 257637, 282836, 307394, 350018]) },
        ]}
      />
    </div>
  </Card>
)

export const MacroSeries = () => (
  <Card>
    <CardHeader title="Macro indicators" sub="FRED · indexed" />
    <div className="card-body">
      <MultiLineChart
        height={240}
        series={[
          { id: 'cpi', name: 'CPI', color: 'var(--viz-4)', points: pts([100, 104.7, 113.0, 117.7, 121.2]) },
          { id: 'gdp', name: 'Real GDP', color: 'var(--viz-5)', points: pts([100, 105.9, 108.0, 110.8, 114.0]) },
        ]}
      />
    </div>
  </Card>
)
