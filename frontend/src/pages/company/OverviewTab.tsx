/** Company-360 consolidated overview from GET /companies/:id/profile/. */
import { useProfile, useTimeseries } from '../../lib/queries'
import { date, fullPrecision, humanize, money } from '../../lib/format'
import { formatDerivedMetric } from '../../lib/finance'
import { Card, CardHeader, EmptyState, Provenance, Query } from '../../components/ui'
import { TrendChart } from '../../components/ui/Chart'
import { KpiHighlights } from './KpiHighlights'

const REVENUE_CHAIN = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax']

function RevenueTrend({ id }: { id: number }) {
  const trend = useTimeseries(id, REVENUE_CHAIN, true)
  if (!trend.data || trend.data.series.length < 2) return null
  const data = [...trend.data.series].reverse().map((p) => ({ x: (p.period_end || '').slice(0, 7), y: p.value }))
  return (
    <Card>
      <CardHeader title="Revenue trend" sub="Annual — resolved across the XBRL tag history" />
      <div className="card-body"><TrendChart data={data} height={200} fmt={(v) => money(v)} /></div>
    </Card>
  )
}

export function OverviewTab({ id }: { id: number }) {
  const profile = useProfile(id)
  return (
    <div className="col gap-4">
      <KpiHighlights id={id} />
      <RevenueTrend id={id} />
      <Query q={profile}>
      {(p) => {
        const metrics = Object.entries(p.financials.derived_metrics)
        return (
          <div className="grid grid-2">
            {/* Identity */}
            <Card>
              <CardHeader title="Identity" sub={<Provenance source={p.identity.provenance.source} />} />
              <div className="card-body col gap-3">
                <KV k="Legal name" v={p.identity.name} />
                <KV k="Ticker" v={p.identity.ticker || '—'} />
                <KV k="Industry (SIC)" v={p.identity.sic_description || p.identity.sic_code || '—'} />
                <KV k="Headquarters" v={[p.identity.hq_state, p.identity.hq_country].filter(Boolean).join(', ') || '—'} />
                {p.identity.identifiers.length > 0 && (
                  <div className="col gap-1">
                    <span className="field-label">Cross-source identifiers</span>
                    <div className="row gap-2 wrap">
                      {p.identity.identifiers.map((idn, i) => (
                        <span key={i} className="badge">{idn.system}: {idn.value}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Financial snapshot */}
            <Card>
              <CardHeader
                title="Financial snapshot"
                sub={<Provenance source={p.financials.provenance.source} asOf={p.financials.provenance.as_of} />}
              />
              {metrics.length === 0 ? (
                <EmptyState title="No derived metrics" message="Sync facts, then compute metrics to populate KPIs." />
              ) : (
                <div className="card-body grid grid-2">
                  {metrics.map(([key, m]) => (
                    <div key={key} className="stat" style={{ padding: 'var(--sp-2)' }}>
                      <div className="stat-label">{humanize(key)}</div>
                      <div className="stat-value" style={{ fontSize: 'var(--fs-xl)' }} title={fullPrecision(m.value, m.unit) || undefined}>{formatDerivedMetric(key, m.value, m.unit)}</div>
                      {m.period_end && <div className="stat-sub">FY {m.period_end.slice(0, 4)}</div>}
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Recent filings */}
            <Card>
              <CardHeader title={`Recent filings (${p.financials.filing_count})`} sub={<Provenance source={p.filings.provenance.source} />} />
              <div className="card-body col gap-2">
                {p.filings.recent.length === 0 ? <span className="muted text-sm">No filings synced.</span> : p.filings.recent.map((f, i) => (
                  <div key={i} className="row between text-sm">
                    <span className="badge badge-info">{f.form_type}</span>
                    <span className="muted mono">{f.accession_number}</span>
                    <span className="muted">{date(f.filing_date)}</span>
                  </div>
                ))}
              </div>
            </Card>

            {/* Recent documents */}
            <Card>
              <CardHeader title="Document highlights" sub={<Provenance source={p.documents.provenance.source} />} />
              <div className="card-body col gap-3">
                {p.documents.recent.length === 0 ? <span className="muted text-sm">No filing documents ingested.</span> : p.documents.recent.map((d, i) => (
                  <div key={i} className="col gap-1">
                    <span className="badge">{d.type || 'document'}{d.file_name ? ` · ${d.file_name}` : ''}</span>
                    {d.snippet && <p className="caption" style={{ lineHeight: 1.5 }}>{d.snippet}…</p>}
                  </div>
                ))}
              </div>
            </Card>

            {/* CRM */}
            {(p.crm.customer_class || p.crm.customer_vertical || p.crm.contract_status) && (
              <Card className="grid-2" >
                <CardHeader title="CRM context" sub={<Provenance source={p.crm.provenance.source} />} />
                <div className="card-body row gap-4 wrap">
                  <KV k="Class" v={p.crm.customer_class || '—'} />
                  <KV k="Type" v={p.crm.customer_type || '—'} />
                  <KV k="Vertical" v={p.crm.customer_vertical || '—'} />
                  <KV k="Contract" v={p.crm.contract_status || '—'} />
                </div>
              </Card>
            )}
          </div>
        )
      }}
      </Query>
    </div>
  )
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="col gap-1">
      <span className="field-label">{k}</span>
      <span>{v}</span>
    </div>
  )
}
