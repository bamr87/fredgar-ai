/** Company-360 detail: identity header + tabbed views (Overview, Financials,
 *  Macro overlay, Filings & Documents, Leadership, Facts). */
import { useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '../lib/app-context'
import { useCompany, useComputeMetrics, useSyncFacts, useSyncStatus, useSyncSubmissions } from '../lib/queries'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { recordRecent } from '../lib/recent'
import { useToast } from '../lib/toast'
import { cik10, relTime, secCompanyUrl } from '../lib/format'
import {
  Badge,
  Button,
  ErrorState,
  IconChart,
  IconExternal,
  IconFile,
  IconGlobe,
  IconLayers,
  IconRefresh,
  IconUsers,
  Loading,
  Tabs,
} from '../components/ui'
import { OverviewTab } from './company/OverviewTab'
import { FinancialsTab } from './company/FinancialsTab'
import { MacroOverlayTab } from './company/MacroOverlayTab'
import { FilingsTab } from './company/FilingsTab'
import { LeadershipTab } from './company/LeadershipTab'
import { FactsTab } from './company/FactsTab'

const TAB_KEYS = ['overview', 'financials', 'macro', 'filings', 'leadership', 'facts']

export function CompanyDetail() {
  const { id } = useParams()
  const companyId = Number(id)
  const company = useCompany(Number.isFinite(companyId) ? companyId : null)
  const [params, setParams] = useSearchParams()
  // Fall back to 'overview' for unknown/garbage ?tab= values so the content area never blanks.
  const rawTab = params.get('tab') || 'overview'
  const tab = TAB_KEYS.includes(rawTab) ? rawTab : 'overview'
  const setTab = (t: string) => setParams((p) => { p.set('tab', t); return p }, { replace: true })
  useDocumentTitle(company.data?.name)

  const cdata = company.data
  useEffect(() => {
    if (cdata) recordRecent({ id: cdata.id, name: cdata.name, ticker: cdata.ticker, cik: cdata.cik })
  }, [cdata])

  if (company.isPending) return <div className="page"><Loading label="Loading company…" /></div>
  if (company.isError || !company.data) return <div className="page"><ErrorState error={company.error} /></div>

  const c = company.data
  const tabs = [
    { key: 'overview', label: 'Overview', icon: <IconLayers width={16} height={16} /> },
    { key: 'financials', label: 'Financials', icon: <IconChart width={16} height={16} /> },
    { key: 'macro', label: 'Macro', icon: <IconGlobe width={16} height={16} /> },
    { key: 'filings', label: 'Filings & Docs', icon: <IconFile width={16} height={16} /> },
    { key: 'leadership', label: 'Leadership', icon: <IconUsers width={16} height={16} /> },
    { key: 'facts', label: 'XBRL Facts', icon: <IconLayers width={16} height={16} /> },
  ]

  return (
    <div className="page">
      {/* Identity header */}
      <div className="row between wrap gap-3" style={{ marginBottom: 'var(--sp-3)' }}>
        <div className="row gap-3">
          <div className="brand-mark" style={{ width: 52, height: 52, fontSize: 20, borderRadius: 12 }}>
            {(c.ticker || c.name).slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div className="page-title">
              <h1 style={{ fontSize: 'var(--fs-2xl)' }}>{c.name}</h1>
              {c.ticker && <Badge tone="accent">{c.ticker}</Badge>}
            </div>
            <div className="row gap-3 wrap caption mt-2">
              <span className="mono">CIK {cik10(c.cik)}</span>
              {c.sic_description && (
                <Link to={`/companies?sic_code=${encodeURIComponent(c.sic_code || '')}`} title="View companies in this industry">{c.sic_description} ›</Link>
              )}
              {(c.hq_city || c.hq_state || c.hq_country) && (
                c.hq_state
                  ? <Link to={`/companies?hq_state=${encodeURIComponent(c.hq_state)}`} title="View companies in this state">{[c.hq_city, c.hq_state, c.hq_country].filter(Boolean).join(', ')} ›</Link>
                  : <span>{[c.hq_city, c.hq_state, c.hq_country].filter(Boolean).join(', ')}</span>
              )}
              <a href={secCompanyUrl(c.cik)} target="_blank" rel="noreferrer" className="row gap-1">
                SEC EDGAR <IconExternal width={12} height={12} />
              </a>
            </div>
          </div>
        </div>
        <div className="col gap-2" style={{ alignItems: 'flex-end' }}>
          <Link to="/companies" className="link-btn text-sm">← All companies</Link>
          <SyncBadge id={companyId} />
        </div>
      </div>

      <AdminBar id={companyId} />

      <div className="mt-3">
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
      </div>

      <div className="mt-4">
        {tab === 'overview' && <OverviewTab id={companyId} />}
        {tab === 'financials' && <FinancialsTab id={companyId} />}
        {tab === 'macro' && <MacroOverlayTab id={companyId} />}
        {tab === 'filings' && <FilingsTab id={companyId} cik={c.cik} />}
        {tab === 'leadership' && <LeadershipTab id={companyId} />}
        {tab === 'facts' && <FactsTab id={companyId} />}
      </div>
    </div>
  )
}

function SyncBadge({ id }: { id: number }) {
  const status = useSyncStatus(id)
  if (!status.data) return null
  const { facts_synced_at, submissions_synced_at } = status.data
  const last = facts_synced_at || submissions_synced_at
  return (
    <span className="provenance text-xs">
      {last ? `Synced ${relTime(last)}` : 'Never synced'}
    </span>
  )
}

/** Admin-only sync/compute toolbar (visible only with a token). */
function AdminBar({ id }: { id: number }) {
  const { isAdmin } = useApp()
  const toast = useToast()
  const subs = useSyncSubmissions(id)
  const facts = useSyncFacts(id)
  const metrics = useComputeMetrics(id)
  if (!isAdmin) return null

  const busy = subs.isPending || facts.isPending || metrics.isPending
  const err = subs.error || facts.error || metrics.error
  const fail = (e: unknown) => toast.error((e as Error).message)

  return (
    <div className="card card-pad mt-2" style={{ background: 'var(--c-surface-2)' }}>
      <div className="row between wrap gap-3">
        <div className="row gap-2 wrap">
          <Badge tone="pos" dot>admin</Badge>
          <span className="caption">Pull fresh data from SEC EDGAR (rate-limited).</span>
        </div>
        <div className="row gap-2 wrap">
          <Button size="sm" loading={subs.isPending} disabled={busy} onClick={() => subs.mutate(undefined, { onSuccess: (d) => toast.success(`Filings synced (${d.filings_processed ?? '—'}).`), onError: fail })}>
            <IconRefresh width={14} height={14} /> Sync filings
          </Button>
          <Button size="sm" loading={facts.isPending} disabled={busy} onClick={() => facts.mutate(undefined, { onSuccess: (d) => toast.success(`Facts loaded (${d.facts_loaded ?? '—'}).`), onError: fail })}>
            <IconRefresh width={14} height={14} /> Sync facts
          </Button>
          <Button size="sm" variant="primary" loading={metrics.isPending} disabled={busy} onClick={() => metrics.mutate(undefined, { onSuccess: (d) => toast.success(`${d.metrics_written} metrics computed.`), onError: fail })}>
            Compute metrics
          </Button>
        </div>
      </div>
      {(subs.data || facts.data || metrics.data) && (
        <div className="caption mt-2 pos">
          {subs.data && `Filings processed: ${subs.data.filings_processed ?? '—'}. `}
          {facts.data && `Facts loaded: ${facts.data.facts_loaded ?? '—'}. `}
          {metrics.data && `Metrics written: ${metrics.data.metrics_written}.`}
        </div>
      )}
      {err && <div className="caption mt-2 neg">{(err as Error).message}</div>}
    </div>
  )
}
