/** Typed endpoint functions for every API resource used by the UI. */
import { httpGet, httpPost, qs } from './http'
import type {
  BundleObservations,
  CohortCompare,
  Company,
  CompanyMetadata,
  CompanyProfile,
  DerivedMetric,
  DocumentSearchResponse,
  EdgarSearchResponse,
  Facets,
  Fact,
  FactsFacets,
  Filing,
  FinancialStatement,
  Health,
  LatestByConcepts,
  Leadership,
  LeadershipAnalysis,
  LeadershipCompare,
  Paginated,
  PeerFactCompare,
  PeerGroup,
  SeriesBundle,
  SicResponse,
  StakeholderAssessment,
  StatementType,
  SyncStatus,
  TaskStatus,
  Timeseries,
} from './types'

const V = '/api/v1'

// ---- Health & reference ----
export const getHealth = () => httpGet<Health>(`${V}/health/`)
// Root readiness probe (UPS-BE-11); Vite and nginx proxy it beside /api.
export const getReady = () => httpGet<Health>('/readyz')
export const getSicCodes = (p: { q?: string; code?: string; limit?: number }) =>
  httpGet<SicResponse>(`${V}/reference/sic-codes/${qs({ ...p, limit: p.limit ?? 40 })}`)

// ---- Companies ----
export const listCompanies = (p: {
  page?: number
  search?: string
  ordering?: string
  ticker?: string
  cik?: string
  industry?: string
  sic_code?: string
  hq_state?: string
}) => httpGet<Paginated<Company>>(`${V}/companies/${qs(p)}`)

export const getCompany = (id: number) => httpGet<Company>(`${V}/companies/${id}/`)

export const edgarSearch = (q: string, limit = 25) =>
  httpGet<EdgarSearchResponse>(`${V}/companies/edgar-search/${qs({ q, limit })}`)

export const companyFromEdgar = (body: { ticker?: string; cik?: string; name?: string }) =>
  httpPost<Company>(`${V}/companies/from-edgar/`, body)

export const bulkFromEdgar = (body: { update_existing?: boolean; refresh_sec_json?: boolean }) =>
  httpPost<{ companies_inserted: number; companies_updated: number; errors: number; message: string }>(
    `${V}/companies/bulk-from-edgar-tickers/`,
    body,
  )

export const getSyncStatus = (id: number) => httpGet<SyncStatus>(`${V}/companies/${id}/edgar-sync-status/`)

export const syncSubmissions = (id: number, async = false) =>
  httpPost<{ company: number; filings_processed?: number; task_id?: string; status?: string }>(
    `${V}/companies/${id}/sync-submissions/${qs({ async })}`,
  )

export const syncFacts = (id: number, async = false) =>
  httpPost<{ company: number; facts_loaded?: number; task_id?: string; status?: string }>(
    `${V}/companies/${id}/sync-facts/${qs({ async })}`,
  )

export const computeMetrics = (id: number) =>
  httpPost<{ company: number; metrics_written: number }>(`${V}/companies/${id}/compute-metrics/`)

export const getProfile = (id: number) => httpGet<CompanyProfile>(`${V}/companies/${id}/profile/`)

export const getLatestByConcepts = (id: number, concepts: string[], taxonomy = 'us-gaap') =>
  httpGet<LatestByConcepts>(`${V}/companies/${id}/analytics/latest-by-concepts/${qs({ concepts: concepts.join(','), taxonomy })}`)

export const getTimeseries = (id: number, concepts: string[], opts?: { taxonomy?: string; limit?: number; annual?: boolean }) =>
  httpGet<Timeseries>(
    `${V}/companies/${id}/analytics/timeseries/${qs({
      concepts: concepts.join(','),
      taxonomy: opts?.taxonomy ?? 'us-gaap',
      limit: opts?.limit ?? 80,
      annual: opts?.annual ? 'true' : undefined,
    })}`,
  )

export const getStatement = (id: number, statementType: StatementType, taxonomy = 'us-gaap') =>
  httpGet<FinancialStatement>(`${V}/companies/${id}/statements/${qs({ statement_type: statementType, taxonomy })}`)

export const cohortCompare = (p: { concept: string; group_by?: string; taxonomy?: string }) =>
  httpGet<CohortCompare>(`${V}/companies/compare/${qs(p)}`)

// ---- Leadership ----
export const getLeadership = (id: number) => httpGet<Leadership>(`${V}/companies/${id}/leadership/`)
export const getStakeholder = (id: number) => httpGet<StakeholderAssessment>(`${V}/companies/${id}/stakeholder-assessment/`)
export const leadershipCompare = (ciks: string[]) =>
  httpGet<LeadershipCompare>(`${V}/companies/leadership-compare/${qs({ ciks: ciks.join(',') })}`)
export const getLeadershipAnalysis = (id: number) =>
  httpGet<LeadershipAnalysis>(`${V}/companies/${id}/leadership-analysis/`)
export const analyzeLeadership = (id: number) =>
  httpPost<LeadershipAnalysis>(`${V}/companies/${id}/analyze-leadership/`)

// ---- Filings, documents, facts ----
export const listFilings = (p: { company?: number; page?: number; form_type?: string; ordering?: string; search?: string }) =>
  httpGet<Paginated<Filing>>(`${V}/filings/${qs(p)}`)

export const ingestSubmission = (body: { url: string; ticker?: string; cik?: string }) =>
  httpPost<{ filing: number; documents_ingested: number }>(`${V}/filings/ingest-submission/`, body)

export const ingestHtm = (body: { url: string; ticker?: string; cik?: string }) =>
  httpPost<Filing>(`${V}/filings/ingest-htm/`, body)

export const searchDocuments = (p: { q: string; form_type?: string; cik?: string }) =>
  httpGet<DocumentSearchResponse>(`${V}/filings/search/${qs(p)}`)

export const getFactsFacets = (companyId: number) =>
  httpGet<FactsFacets>(`${V}/facts/facets/${qs({ company: companyId })}`)

export const listFacts = (p: { company?: number; page?: number; concept?: string; taxonomy?: string; ordering?: string; search?: string }) =>
  httpGet<Paginated<Fact>>(`${V}/facts/${qs(p)}`)

export const listDerivedMetrics = (p: { company?: number; key?: string; page?: number }) =>
  httpGet<Paginated<DerivedMetric>>(`${V}/derived-metrics/${qs(p)}`)

// ---- Metadata + facets ----
export const getFacets = () => httpGet<Facets>(`${V}/company-metadata/facets/`)
export const listMetadata = (p: {
  page?: number
  page_size?: number
  search?: string
  ordering?: string
  hq_state?: string
  hq_country?: string
  sic_code?: string
  sic_description?: string
  industry?: string
  customer_vertical?: string
}) => httpGet<Paginated<CompanyMetadata>>(`${V}/company-metadata/${qs(p)}`)

// ---- Peer groups ----
export const listPeerGroups = (p?: { page?: number; search?: string }) =>
  httpGet<Paginated<PeerGroup>>(`${V}/peer-groups/${qs(p ?? {})}`)
export const getPeerGroup = (id: number) => httpGet<PeerGroup>(`${V}/peer-groups/${id}/`)
export const peerFactCompare = (id: number, concept: string, taxonomy = 'us-gaap') =>
  httpGet<PeerFactCompare>(`${V}/peer-groups/${id}/analytics/peer-fact-compare/${qs({ concept, taxonomy })}`)

// ---- Macro / public series ----
export const listSeriesBundles = (p?: { page?: number }) =>
  httpGet<Paginated<SeriesBundle>>(`${V}/series-bundles/${qs(p ?? {})}`)
export const getBundleObservations = (slug: string, perSeries = 2000) =>
  httpGet<BundleObservations>(`${V}/series-bundles/${slug}/observations/${qs({ per_series: perSeries })}`)

// ---- Tasks ----
export const getTask = (taskId: string) => httpGet<TaskStatus>(`${V}/tasks/${taskId}/`)
