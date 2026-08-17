import { Stat } from 'frontend'

export const MetricRow = () => (
  <div className="grid grid-4">
    <Stat label="Revenue (FY2024)" value="$391.0B" sub="+2.0% vs FY2023" />
    <Stat label="Gross margin" value="46.2%" sub="+1.8 pts YoY" />
    <Stat label="Filings ingested" value="1,284" sub="Last sync 2 hours ago" />
    <Stat label="Facts stored" value="612,940" sub="Across 38 statements" />
  </div>
)

export const Accented = () => (
  <div className="grid grid-3">
    <Stat label="Free cash flow" value="$108.8B" sub="+9.3% YoY" accent="var(--c-positive)" />
    <Stat label="Total debt" value="$106.6B" sub="-4.1% YoY" accent="var(--c-negative)" />
    <Stat label="R&D intensity" value="8.0%" sub="of revenue" accent="var(--c-accent)" />
  </div>
)

export const Minimal = () => (
  <div className="grid grid-2">
    <Stat label="Companies tracked" value="503" />
    <Stat label="Peer groups" value="12" />
  </div>
)
