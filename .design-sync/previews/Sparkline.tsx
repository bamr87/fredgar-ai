import { Card, Sparkline } from 'frontend'

const series = (vals: number[]) => vals.map((y, i) => ({ x: `FY${2017 + i}`, y }))

export const InTableCells = () => (
  <Card>
    <table className="tbl">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Revenue trend</th>
          <th className="td-num">FY2024</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td className="mono">AAPL</td>
          <td style={{ width: 160 }}>
            <Sparkline data={series([229, 265, 260, 274, 365, 394, 383, 391])} />
          </td>
          <td className="td-num">$391.0B</td>
        </tr>
        <tr>
          <td className="mono">NVDA</td>
          <td style={{ width: 160 }}>
            <Sparkline data={series([9, 11, 10, 16, 26, 26, 60, 130])} color="var(--c-positive)" />
          </td>
          <td className="td-num">$130.5B</td>
        </tr>
        <tr>
          <td className="mono">INTC</td>
          <td style={{ width: 160 }}>
            <Sparkline data={series([62, 70, 71, 77, 79, 63, 54, 53])} color="var(--c-negative)" />
          </td>
          <td className="td-num">$53.1B</td>
        </tr>
      </tbody>
    </table>
  </Card>
)

export const OnAStatTile = () => (
  <div className="grid grid-2">
    <Card>
      <div className="stat">
        <div className="stat-label">Revenue</div>
        <div className="stat-value">$391.0B</div>
        <Sparkline data={series([229, 265, 260, 274, 365, 394, 383, 391])} height={36} />
      </div>
    </Card>
    <Card>
      <div className="stat">
        <div className="stat-label">Gross margin</div>
        <div className="stat-value">46.2%</div>
        <Sparkline data={series([38, 38, 38, 38, 41, 43, 44, 46])} color="var(--viz-3)" height={36} />
      </div>
    </Card>
  </div>
)
