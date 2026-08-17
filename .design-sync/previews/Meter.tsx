import { Meter } from 'frontend'

export const ScoreRows = () => (
  <div className="col gap-4" style={{ maxWidth: 480 }}>
    {[
      { label: 'Reinvestment vs payout', value: 0.72 },
      { label: 'Capex / local investment proxy', value: 0.54 },
      { label: 'R&D intensity', value: 0.81 },
      { label: 'Insider alignment', value: 0.33 },
    ].map((r) => (
      <div key={r.label} className="col gap-1">
        <div className="row between">
          <span className="text-sm">{r.label}</span>
          <span className="num text-sm">{(r.value * 100).toFixed(0)}</span>
        </div>
        <Meter value={r.value} />
      </div>
    ))}
  </div>
)

export const Colored = () => (
  <div className="col gap-4" style={{ maxWidth: 480 }}>
    <div className="col gap-1">
      <span className="text-sm">Above peer median</span>
      <Meter value={0.86} color="var(--c-positive)" />
    </div>
    <div className="col gap-1">
      <span className="text-sm">Below peer median</span>
      <Meter value={0.24} color="var(--c-negative)" />
    </div>
    <div className="col gap-1">
      <span className="text-sm">Within one standard deviation</span>
      <Meter value={0.5} color="var(--c-warning)" />
    </div>
  </div>
)

export const CustomRange = () => (
  <div className="col gap-4" style={{ maxWidth: 480 }}>
    <div className="col gap-1">
      <span className="text-sm">Gross margin — 46.2% of a 0–100 scale</span>
      <Meter value={46.2} min={0} max={100} />
    </div>
    <div className="col gap-1">
      <span className="text-sm">Stakeholder index — -1 to +1, currently +0.4</span>
      <Meter value={0.4} min={-1} max={1} color="var(--viz-3)" />
    </div>
  </div>
)
