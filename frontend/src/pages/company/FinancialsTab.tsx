/** Financial statements, derived metrics, trend chart, and period-over-period change. */
import { useState } from 'react'
import { useCompany, useDerivedMetrics, useStatement, useTimeseries } from '../../lib/queries'
import { byUnit, cx, date, fullPrecision, humanize, secFilingUrl, signedPctPoints } from '../../lib/format'
import { TREND_CONCEPTS, formatDerivedMetric, toneClass, withPeriodChange } from '../../lib/finance'
import { downloadCsv } from '../../lib/csv'
import type { StatementType } from '../../lib/types'
import {
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  IconDownload,
  Query,
  Segmented,
} from '../../components/ui'
import { TrendChart } from '../../components/ui/Chart'
import { KpiHighlights } from './KpiHighlights'

const STATEMENTS: { value: StatementType; label: string }[] = [
  { value: 'income_statement', label: 'Income' },
  { value: 'balance_sheet', label: 'Balance Sheet' },
  { value: 'cash_flow_statement', label: 'Cash Flow' },
]

export function FinancialsTab({ id }: { id: number }) {
  const [stmt, setStmt] = useState<StatementType>('income_statement')
  const [conceptKey, setConceptKey] = useState('revenue')
  const trendConcept = TREND_CONCEPTS.find((c) => c.key === conceptKey) ?? TREND_CONCEPTS[0]
  const company = useCompany(id)
  const statement = useStatement(id, stmt)
  const metrics = useDerivedMetrics(id)
  const trend = useTimeseries(id, trendConcept.concepts, trendConcept.annual)
  const cik = company.data?.cik || ''
  const ticker = company.data?.ticker || cik

  const exportStatement = () => {
    if (!statement.data) return
    downloadCsv(
      `${ticker}-${stmt}.csv`,
      statement.data.line_items.map((li) => ({ line_item: li.label, value: li.value, unit: li.unit, accession: li.accession })),
    )
  }

  return (
    <div className="col gap-4">
      <KpiHighlights id={id} />

      <Card>
        <CardHeader
          title="Trend"
          sub={trendConcept.annual ? 'Annual series — change column is year-over-year' : 'Period series — change vs the prior row'}
          actions={
            <select className="select" style={{ width: 'auto' }} value={conceptKey} onChange={(e) => setConceptKey(e.target.value)}>
              {TREND_CONCEPTS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
          }
        />
        <div className="card-body">
          <Query q={trend} isEmpty={(t) => t.series.length === 0} empty={<EmptyState title="No data for this concept" message="This company has no facts for the selected concept yet." />}>
            {(t) => {
              const history = withPeriodChange(t.series)
              const unit = t.series[0]?.unit
              const changeHeader = trendConcept.annual ? 'YoY' : 'Change'
              return (
                <div className="col gap-4">
                  <TrendChart
                    data={[...t.series].reverse().map((p) => ({ x: (p.period_end || '').slice(0, 7), y: p.value }))}
                    fmt={(v) => byUnit(v, unit)}
                  />
                  <DataTable
                    compact
                    rows={history}
                    rowKey={(p, i) => `${p.period_end ?? ''}-${p.period_start ?? ''}-${i}`}
                    columns={[
                      { key: 'end', header: 'Period end', render: (p) => date(p.period_end) },
                      { key: 'start', header: 'Period start', render: (p) => date(p.period_start) },
                      {
                        key: 'value',
                        header: 'Value',
                        align: 'right',
                        render: (p) => <span title={fullPrecision(p.value, p.unit) || undefined}>{byUnit(p.value, p.unit)}</span>,
                      },
                      {
                        key: 'change',
                        header: changeHeader,
                        align: 'right',
                        render: (p) => (
                          <span className={cx(toneClass(p.delta?.direction))}>
                            {p.delta ? signedPctPoints(p.delta.pct) : '—'}
                          </span>
                        ),
                      },
                    ]}
                  />
                </div>
              )
            }}
          </Query>
        </div>
      </Card>

      <div className="grid grid-2">
        <Card>
          <CardHeader
            title="Financial statement"
            actions={
              <div className="row gap-2">
                <Segmented value={stmt} options={STATEMENTS} onChange={setStmt} />
                <Button size="sm" variant="ghost" disabled={!statement.data} onClick={exportStatement} title="Download CSV"><IconDownload width={14} height={14} /></Button>
              </div>
            }
          />
          <Query q={statement} isEmpty={(s) => s.line_items.every((li) => li.value === null)} empty={<EmptyState title="No statement data" message="Sync facts to build statements." />}>
            {(s) => (
              <>
                <div className="caption" style={{ padding: '8px var(--sp-4) 0' }}>
                  Period ending {date(s.period_end)}
                </div>
                <div className="table-wrap">
                  <table className="tbl tbl-compact">
                    <tbody>
                      {s.line_items.map((li) => (
                        <tr key={li.key}>
                          <td>{li.label}</td>
                          <td className="td-num" title={fullPrecision(li.value, li.unit) || undefined}>{byUnit(li.value, li.unit)}</td>
                          <td className="td-num" style={{ width: 60 }}>
                            {li.accession ? <a href={secFilingUrl(cik, li.accession)} target="_blank" rel="noreferrer" className="text-xs">source</a> : ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Query>
        </Card>

        <Card>
          <CardHeader title="Derived metrics" sub="Computed KPIs" />
          <Query q={metrics} isEmpty={(m) => m.results.length === 0} empty={<EmptyState title="No metrics computed" message="Run “Compute metrics” (admin) after syncing facts." />}>
            {(m) => {
              const seen = new Set<string>()
              const latest = m.results.filter((r) => (seen.has(r.key) ? false : (seen.add(r.key), true)))
              return (
                <div className="card-body grid grid-2">
                  {latest.map((r) => {
                    const n = Number(r.value)
                    const margin = r.key.includes('margin')
                    return (
                      <div key={r.id} className="stat" style={{ padding: 'var(--sp-2)' }}>
                        <div className="stat-label">{humanize(r.key)}</div>
                        <div
                          className={cx('stat-value', margin && Number.isFinite(n) && toneClass(n > 0 ? 1 : n < 0 ? -1 : 0))}
                          style={{ fontSize: 'var(--fs-lg)' }}
                        >
                          {formatDerivedMetric(r.key, r.value, r.unit)}
                        </div>
                        {r.period_end && <div className="stat-sub">FY {r.period_end.slice(0, 4)}</div>}
                      </div>
                    )
                  })}
                </div>
              )
            }}
          </Query>
        </Card>
      </div>
    </div>
  )
}
