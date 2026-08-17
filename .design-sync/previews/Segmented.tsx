import { Segmented } from 'frontend'

export const PeriodPicker = () => (
  <Segmented
    value="annual"
    options={[
      { value: 'annual', label: 'Annual' },
      { value: 'quarterly', label: 'Quarterly' },
    ]}
    onChange={() => {}}
  />
)

export const StatementPicker = () => (
  <Segmented
    value="balance"
    options={[
      { value: 'income', label: 'Income' },
      { value: 'balance', label: 'Balance sheet' },
      { value: 'cash', label: 'Cash flow' },
    ]}
    onChange={() => {}}
  />
)

export const UnitPicker = () => (
  <div className="row gap-3 wrap">
    <Segmented
      value="usd"
      options={[
        { value: 'usd', label: '$' },
        { value: 'pct', label: '%' },
        { value: 'yoy', label: 'YoY' },
      ]}
      onChange={() => {}}
    />
    <Segmented
      value="table"
      options={[
        { value: 'table', label: 'Table' },
        { value: 'chart', label: 'Chart' },
      ]}
      onChange={() => {}}
    />
  </div>
)
