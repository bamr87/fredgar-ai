/** TypeScript mirror of the Django/DRF API contract (`/api/v1`). */

export type Paginated<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type ProvenanceTag = { source: string; as_of?: string | null }

// ---- Companies ----
export type Company = {
  id: number
  cik: string
  ticker: string | null
  name: string
  industry: string | null
  sic_code: string | null
  sic_description: string | null
  naics_code: string | null
  hq_state: string | null
  hq_country: string
  hq_city: string | null
  headquarters: string | null
  size: string | null
  management: Record<string, unknown>
  locations: unknown[]
  business_units: unknown[]
  product_types: unknown[]
  extra_attributes: Record<string, unknown>
  crm_external_key: string | null
  customer_class: string | null
  customer_type: string | null
  customer_vertical: string | null
  contract_status: string | null
  created_at: string
  updated_at: string
}

export type CompanyMetadata = {
  id: number
  cik: string
  ticker: string | null
  name: string
  industry: string | null
  sic_code: string | null
  sic_description: string | null
  naics_code: string | null
  hq_state: string | null
  hq_country: string
  hq_city: string | null
  headquarters: string | null
  size: string | null
  crm_external_key: string | null
  customer_class: string | null
  customer_type: string | null
  customer_vertical: string | null
  contract_status: string | null
  created_at: string
  updated_at: string
}

export type Facets = {
  totals: { companies: number; with_sic_code: number; with_naics_code: number; with_industry_text: number }
  top_sic: { sic_code: string; sic_description: string; count: number }[]
  hq_state: { hq_state: string; count: number }[]
  industry: { industry: string; count: number }[]
  hq_country: { hq_country: string; count: number }[]
}

export type EdgarSearchResult = { cik: string; ticker: string | null; name: string; in_warehouse: boolean }
export type EdgarSearchResponse = { count: number; results: EdgarSearchResult[] }

export type SyncStatus = {
  company: number
  submissions_synced_at: string | null
  facts_synced_at: string | null
  last_error: string
}

// ---- Profile (Company-360) ----
export type CompanyProfile = {
  company: number
  identity: {
    cik: string
    ticker: string | null
    name: string
    sic_code: string | null
    sic_description: string | null
    hq_state: string | null
    hq_country: string | null
    industry: string | null
    identifiers: { system: string; value: string; confidence: number }[]
    provenance: ProvenanceTag
  }
  financials: {
    derived_metrics: Record<string, { value: number | null; unit: string | null; period_end: string | null }>
    filing_count: number
    provenance: ProvenanceTag
  }
  filings: {
    recent: { accession_number: string; form_type: string; filing_date: string | null }[]
    provenance: ProvenanceTag
  }
  documents: {
    recent: { type: string | null; file_name: string | null; snippet: string }[]
    provenance: ProvenanceTag
  }
  crm: {
    customer_class: string | null
    customer_type: string | null
    customer_vertical: string | null
    contract_status: string | null
    provenance: ProvenanceTag
  }
}

// ---- Analytics ----
export type LatestValue = {
  concept: string
  period_end: string | null
  period_start: string | null
  value: number | null
  unit: string | null
  dimensions: Record<string, unknown>
}
export type LatestByConcepts = { company: number; taxonomy: string; values: Record<string, LatestValue> }

export type TimeseriesPoint = {
  period_end: string | null
  period_start: string | null
  value: number | null
  unit: string | null
  concept?: string
  dimensions: Record<string, unknown>
}
export type Timeseries = { company: number; concept: string; concepts?: string[]; taxonomy: string; series: TimeseriesPoint[] }

// ---- Statements & metrics ----
export type StatementLineItem = { key: string; label: string; value: number | null; unit: string | null; accession: string | null }
export type FinancialStatement = {
  company: number
  statement_type: string
  taxonomy: string
  period_end: string | null
  line_items: StatementLineItem[]
}
export type StatementType = 'income_statement' | 'balance_sheet' | 'cash_flow_statement'

export type DerivedMetric = {
  id: number
  company: number
  key: string
  period_end: string | null
  value: string | null
  unit: string
  extra: Record<string, unknown>
  computed_at: string
}

// ---- Cohort compare ----
export type CohortGroupRow = { group: string; company_count: number; avg: number; min: number; max: number; sum: number }
export type CohortCompare = { group_by: string; concept: string; taxonomy: string; groups: CohortGroupRow[] }

// ---- Filings & documents ----
export type Filing = {
  id: number
  company: number
  accession_number: string
  form_type: string
  filing_date: string | null
  period_of_report: string | null
  url: string | null
  local_path: string | null
  metadata: Record<string, unknown>
}
export type DocumentSearchHit = {
  id: number
  filing: number
  company: number
  cik: string
  form_type: string
  type: string
  sequence: number
  file_name: string
  snippet: string
}
export type DocumentSearchResponse = { count: number; query: string; results: DocumentSearchHit[] }

export type FactsFacets = {
  company: number
  taxonomy_counts: { taxonomy: string; c: number }[]
  top_concepts: { concept: string; c: number }[]
  facts_by_period_year: { year: number; count: number }[]
}
export type Fact = {
  id: number
  company: number
  taxonomy: string
  concept: string
  period_start: string | null
  period_end: string | null
  unit: string | null
  value: number | null
  dimensions: Record<string, unknown>
}

// ---- Leadership & stakeholder ----
export type LeadershipPerson = {
  name: string
  person_cik: string | null
  title: string
  is_director: boolean
  is_officer: boolean
  is_ten_percent_owner: boolean
  first_seen: string | null
  last_seen: string | null
  filings_count: number
  net_insider_shares: number
  source: string
}
export type Leadership = { company: number; count: number; leadership: LeadershipPerson[] }

export type StakeholderSignal = {
  name: string
  label: string
  value: number
  score: number
  weight: number
  inputs: { concept: string; period_end: string | null; value: number }[]
  note: string
}
export type StakeholderAssessment = {
  company: number
  period_end: string | null
  orientation_index: number | null
  label: string
  signals: StakeholderSignal[]
  method_version: string
  caveats: string
}

export type LeadershipCompareRow = {
  cik: string
  name: string
  ticker: string | null
  leadership_count: number
  key_people: { name: string; title: string }[]
  orientation_index: number | null
  orientation_label: string
}
export type LeadershipCompare = { count: number; results: LeadershipCompareRow[]; caveats: string }

export type LeadershipInitiative = { title: string; description: string; source: string }
export type LeadershipQuote = { text: string; speaker?: string; source: string }
export type LeadershipAnalysis = {
  company: number
  available?: boolean
  enabled: boolean
  backend?: string
  model_name?: string
  summary: string
  initiatives: LeadershipInitiative[]
  quotes: LeadershipQuote[]
  direction: string
  used_sources: { tag: string; accession: string; type: string }[]
  error?: string
  created_at?: string
  detail?: string
  note?: string
  caveats: string
}

// ---- Peer groups ----
export type PeerGroup = { id: number; name: string; description: string; created_at: string }
export type PeerFactCompare = {
  peer_group: number
  concept: string
  taxonomy: string
  rows: { cik: string; ticker: string | null; name: string; value: number | null; period_end: string | null }[]
}

// ---- Macro series (public data) ----
export type ExternalSeries = {
  id: number
  provider: string
  external_id: string
  title: string
  frequency: string
  units: string
  metadata: Record<string, unknown>
  last_synced_at: string | null
  created_at: string
}
export type SeriesObservation = {
  id: number
  series: number
  observation_date: string
  value: string
  source_url: string | null
  retrieved_at: string
}
export type SeriesBundle = { id: number; slug: string; name: string; description: string }
export type BundleSeriesMeta = {
  external_id: string
  title: string
  units: string
  frequency: string
  note: string
  industries: string[]
}
export type BundleObservations = {
  bundle: string
  name?: string
  description?: string
  count: number
  series: BundleSeriesMeta[]
  observations: { series: string; provider: string; date: string; value: string }[]
}

// ---- Async tasks ----
export type TaskStatus = {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | string
  ready: boolean
  result?: unknown
  error?: string
}

// ---- Health & reference ----
/** `/healthz` and `/readyz`: each check is `ok`, `skipped` or an `error: …` string. */
export type Health = { status: 'ok' | 'degraded' | string; checks?: Record<string, string> }
export type SicCode = { code: string; description?: string; office?: string; industry_title?: string }
export type SicResponse = { count: number; results: SicCode[] }
