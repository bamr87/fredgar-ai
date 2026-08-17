import { BarsChart, Card, CardHeader } from 'frontend'

const peers = [
  { x: 'NVDA', y: 75.0 },
  { x: 'MSFT', y: 69.8 },
  { x: 'GOOGL', y: 58.2 },
  { x: 'AMZN', y: 48.8 },
  { x: 'AAPL', y: 46.2 },
]

export const PeerComparison = () => (
  <Card>
    <CardHeader title="Gross margin vs peers" sub="FY2024 · percent" />
    <div className="card-body">
      <BarsChart data={peers} fmt={(v) => `${v.toFixed(1)}%`} />
    </div>
  </Card>
)

export const ColorCoded = () => (
  <Card>
    <CardHeader title="Revenue growth" sub="YoY · green above zero, red below" />
    <div className="card-body">
      <BarsChart
        data={[
          { x: 'FY2020', y: 5.5 },
          { x: 'FY2021', y: 33.3 },
          { x: 'FY2022', y: 7.8 },
          { x: 'FY2023', y: -2.8 },
          { x: 'FY2024', y: 2.0 },
        ]}
        colorBy={(p) => ((p.y ?? 0) >= 0 ? 'var(--c-positive)' : 'var(--c-negative)')}
        fmt={(v) => `${v.toFixed(1)}%`}
        height={220}
      />
    </div>
  </Card>
)
