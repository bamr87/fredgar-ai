/** Landing page: coverage overview, market snapshot, recent companies, entry points. */
import { Link, useNavigate } from 'react-router-dom'
import { useBundleObservations, useFacets, usePrefetchCompany } from '../lib/queries'
import { cik10, compact, fullNum, signed } from '../lib/format'
import { applyRange, changeOver, seriesPoints } from '../lib/macro'
import { useRecentCompanies } from '../lib/recent'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { CompanySearch } from '../components/CompanySearch'
import {
  Card,
  CardHeader,
  IconBuilding,
  IconCompare,
  IconGlobe,
  IconSearch,
  Meter,
  Query,
  Stat,
} from '../components/ui'
import { Sparkline } from '../components/ui/Chart'

const QUICK_LINKS = [
  { to: '/companies', icon: <IconBuilding />, title: 'Company Explorer', desc: 'Filter & browse the warehouse' },
  { to: '/search', icon: <IconSearch />, title: 'Filing Search', desc: 'Full-text search of filing documents' },
  { to: '/compare', icon: <IconCompare />, title: 'Compare Cohorts', desc: 'Benchmark a metric across a group' },
  { to: '/macro', icon: <IconGlobe />, title: 'Macro Series', desc: 'FRED economic time series' },
]

export function Dashboard() {
  const facets = useFacets()
  const navigate = useNavigate()
  const recent = useRecentCompanies()
  const prefetch = usePrefetchCompany()
  useDocumentTitle('Dashboard')

  return (
    <div className="page">
      {/* Hero */}
      <Card className="card-pad">
        <div style={{ maxWidth: 720, margin: '0 auto', textAlign: 'center', padding: 'var(--sp-4) 0' }}>
          <h1 style={{ fontSize: 'var(--fs-3xl)' }}>Explore SEC company intelligence</h1>
          <p className="page-desc" style={{ margin: '8px auto var(--sp-4)', maxWidth: '58ch' }}>
            Filings, XBRL financials, derived KPIs, leadership, and a transparent stakeholder index —
            consolidated into a 360° view per company.
          </p>
          <div style={{ maxWidth: 560, margin: '0 auto' }}>
            <CompanySearch autoFocus />
          </div>
        </div>
      </Card>

      {recent.length > 0 && (
        <Card className="mt-4">
          <CardHeader title="Recently viewed" sub="Companies opened on this device" />
          <div className="card-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(14rem, 1fr))', gap: 'var(--sp-2)' }}>
            {recent.map((c) => (
              <Link
                key={c.id}
                to={`/companies/${c.id}`}
                className="card card-hover card-pad"
                style={{ textDecoration: 'none', color: 'inherit' }}
                onMouseEnter={() => prefetch(c.id)}
              >
                <div style={{ fontWeight: 650 }} className="truncate">{c.name}</div>
                <div className="caption">{c.ticker || '—'} · CIK {cik10(c.cik)}</div>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* Coverage stats */}
      <div className="grid grid-4 mt-4">
        <Query q={facets}>
          {(f) => (
            <>
              <Stat label="Companies" value={fullNum(f.totals.companies)} sub="in the warehouse" />
              <Stat label="With SIC code" value={fullNum(f.totals.with_sic_code)} sub={`${pctOf(f.totals.with_sic_code, f.totals.companies)} classified`} />
              <Stat label="With NAICS" value={fullNum(f.totals.with_naics_code)} sub={`${pctOf(f.totals.with_naics_code, f.totals.companies)} coverage`} />
              <Stat label="With industry text" value={fullNum(f.totals.with_industry_text)} sub={`${pctOf(f.totals.with_industry_text, f.totals.companies)} labeled`} />
            </>
          )}
        </Query>
      </div>

      {/* Quick links */}
      <div className="grid grid-4 mt-4">
        {QUICK_LINKS.map((l) => (
          <Link key={l.to} to={l.to} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Card hover className="card-pad">
              <div className="row gap-3">
                <div className="brand-mark" style={{ background: 'var(--c-accent-soft)', color: 'var(--c-accent-text)' }}>{l.icon}</div>
                <div>
                  <div style={{ fontWeight: 650 }}>{l.title}</div>
                  <div className="caption">{l.desc}</div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>

      {/* Breakdowns */}
      <div className="grid grid-2 mt-4">
        <Card>
          <CardHeader title="Top industries" sub="By SIC classification — click to filter" icon={<IconBuilding width={16} height={16} />} />
          <Query q={facets} isEmpty={(f) => f.top_sic.length === 0} empty={<EmptyBlock />}>
            {(f) => (
              <div className="card-body col gap-3">
                {f.top_sic.slice(0, 8).map((s) => {
                  const max = f.top_sic[0]?.count || 1
                  return (
                    <Link key={s.sic_code} to={`/companies?sic_code=${encodeURIComponent(s.sic_code)}`} className="drill-row col gap-1" style={{ color: 'inherit', textDecoration: 'none' }}>
                      <div className="row between text-sm">
                        <span className="truncate drill-label" style={{ maxWidth: '70%' }}>{s.sic_description || `SIC ${s.sic_code}`}</span>
                        <span className="num muted">{fullNum(s.count)} ›</span>
                      </div>
                      <Meter value={s.count} max={max} />
                    </Link>
                  )
                })}
              </div>
            )}
          </Query>
        </Card>

        <MarketSnapshot onOpen={() => navigate('/macro')} />
      </div>
    </div>
  )
}

const SNAPSHOT = [
  { id: 'DGS10', label: '10Y Treasury', mode: 'level' as const },
  { id: 'FEDFUNDS', label: 'Fed Funds Rate', mode: 'level' as const },
  { id: 'UNRATE', label: 'Unemployment', mode: 'level' as const },
  { id: 'CPIAUCSL', label: 'CPI (YoY)', mode: 'yoy' as const },
]

function MarketSnapshot({ onOpen }: { onOpen: () => void }) {
  const obs = useBundleObservations('core')
  return (
    <Card hover>
      <CardHeader title="Market snapshot" sub="Key macro indicators (FRED)" icon={<IconGlobe width={16} height={16} />} actions={<button className="link-btn text-sm" onClick={onOpen}>All series →</button>} />
      <Query q={obs} isEmpty={(d) => d.observations.length === 0} empty={<EmptyBlock />}>
        {(d) => (
          <div className="card-body grid grid-2">
            {SNAPSHOT.map((cfg) => {
              const pts = seriesPoints(d, cfg.id)
              if (pts.length === 0) return null
              const last = pts[pts.length - 1]
              const chg = changeOver(pts, 365)
              const spark = applyRange(pts, '3').map((p) => ({ x: p.date, y: p.value }))
              const headline = cfg.mode === 'yoy' ? (chg.pct != null ? `${chg.pct >= 0 ? '+' : ''}${chg.pct.toFixed(1)}%` : '—') : compact(last.value)
              const sub = cfg.mode === 'yoy' ? `${compact(last.value)} index` : (chg.abs != null ? `${signed(chg.abs, (n) => n.toFixed(2))} 1Y` : '')
              return (
                <div
                  key={cfg.id}
                  className="col gap-1"
                  style={{ padding: 'var(--sp-2)', cursor: 'pointer' }}
                  role="button"
                  tabIndex={0}
                  aria-label={`${cfg.label}: open in Macro Series`}
                  onClick={onOpen}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onOpen()
                    }
                  }}
                >
                  <div className="stat-label">{cfg.label}</div>
                  <div className="row between" style={{ alignItems: 'flex-end' }}>
                    <div>
                      <div className="num" style={{ fontWeight: 680, fontSize: 'var(--fs-xl)' }}>{headline}</div>
                      <div className="caption">{sub}</div>
                    </div>
                    <div style={{ width: 70 }}><Sparkline data={spark} width={70} height={34} /></div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Query>
    </Card>
  )
}

function pctOf(n: number, total: number): string {
  if (!total) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

function EmptyBlock() {
  return (
    <div className="card-body">
      <div className="muted text-sm">No data yet. Add companies and sync from Settings.</div>
    </div>
  )
}
