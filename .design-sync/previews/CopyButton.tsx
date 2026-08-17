import { Card, CopyButton } from 'frontend'

export const Default = () => (
  <div className="row gap-3 wrap">
    <CopyButton text="0000320193" />
    <CopyButton text="https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json" label="Copy API URL" />
  </div>
)

export const NextToAValue = () => (
  <Card>
    <div className="card-pad col gap-3">
      <div className="row between gap-3">
        <div className="col gap-1">
          <span className="caption">CIK</span>
          <span className="mono">0000320193</span>
        </div>
        <CopyButton text="0000320193" />
      </div>
      <div className="row between gap-3">
        <div className="col gap-1">
          <span className="caption">Accession number</span>
          <span className="mono">0000320193-24-000123</span>
        </div>
        <CopyButton text="0000320193-24-000123" />
      </div>
    </div>
  </Card>
)

export const CustomLabel = () => (
  <div className="row gap-3 wrap">
    <CopyButton text="AAPL,MSFT,AMZN,GOOGL,NVDA" label="Copy cohort tickers" />
  </div>
)
