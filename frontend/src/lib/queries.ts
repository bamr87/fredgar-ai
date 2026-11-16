/** TanStack Query hooks — caching, dedup, and loading/error states for every read. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { StatementType } from './types'

const FIVE_MIN = 5 * 60 * 1000

// ---- Health ----
export const useReady = () => useQuery({ queryKey: ['ready'], queryFn: api.getReady, refetchInterval: 30000, retry: false })

// ---- Companies ----
export const useCompanies = (params: Parameters<typeof api.listCompanies>[0]) =>
  useQuery({ queryKey: ['companies', params], queryFn: () => api.listCompanies(params), staleTime: FIVE_MIN })

/** Returns a function to warm the cache for a company (call on hover for instant nav). */
export function usePrefetchCompany() {
  const qc = useQueryClient()
  return (id: number) => {
    qc.prefetchQuery({ queryKey: ['company', id], queryFn: () => api.getCompany(id), staleTime: FIVE_MIN })
    qc.prefetchQuery({ queryKey: ['profile', id], queryFn: () => api.getProfile(id), staleTime: FIVE_MIN })
  }
}

export const useCompany = (id: number | null) =>
  useQuery({ queryKey: ['company', id], queryFn: () => api.getCompany(id as number), enabled: id != null, staleTime: FIVE_MIN })

export const useProfile = (id: number | null) =>
  useQuery({ queryKey: ['profile', id], queryFn: () => api.getProfile(id as number), enabled: id != null, staleTime: FIVE_MIN })

export const useSyncStatus = (id: number | null) =>
  useQuery({ queryKey: ['sync-status', id], queryFn: () => api.getSyncStatus(id as number), enabled: id != null })

export const useEdgarSearch = (q: string) =>
  useQuery({ queryKey: ['edgar-search', q], queryFn: () => api.edgarSearch(q), enabled: q.trim().length >= 2, staleTime: FIVE_MIN })

// ---- Financials ----
export const useStatement = (id: number | null, type: StatementType) =>
  useQuery({ queryKey: ['statement', id, type], queryFn: () => api.getStatement(id as number, type), enabled: id != null, staleTime: FIVE_MIN })

export const useDerivedMetrics = (id: number | null) =>
  useQuery({ queryKey: ['metrics', id], queryFn: () => api.listDerivedMetrics({ company: id as number }), enabled: id != null, staleTime: FIVE_MIN })

export const useTimeseries = (id: number | null, concepts: string[], annual = false) =>
  useQuery({
    queryKey: ['timeseries', id, concepts, annual],
    queryFn: () => api.getTimeseries(id as number, concepts, { annual }),
    enabled: id != null && concepts.length > 0,
    staleTime: FIVE_MIN,
  })

export const useLatestByConcepts = (id: number | null, concepts: string[]) =>
  useQuery({ queryKey: ['latest', id, concepts], queryFn: () => api.getLatestByConcepts(id as number, concepts), enabled: id != null && concepts.length > 0, staleTime: FIVE_MIN })

// ---- Filings / facts ----
export const useFilings = (params: Parameters<typeof api.listFilings>[0]) =>
  useQuery({ queryKey: ['filings', params], queryFn: () => api.listFilings(params), staleTime: FIVE_MIN })

export const useFacts = (params: Parameters<typeof api.listFacts>[0]) =>
  useQuery({ queryKey: ['facts', params], queryFn: () => api.listFacts(params), enabled: params.company != null, staleTime: FIVE_MIN })

export const useFactsFacets = (id: number | null) =>
  useQuery({ queryKey: ['facts-facets', id], queryFn: () => api.getFactsFacets(id as number), enabled: id != null, staleTime: FIVE_MIN })

export const useDocumentSearch = (params: { q: string; form_type?: string; cik?: string }) =>
  useQuery({ queryKey: ['doc-search', params], queryFn: () => api.searchDocuments(params), enabled: params.q.trim().length >= 2, staleTime: FIVE_MIN })

// ---- Leadership ----
export const useLeadership = (id: number | null) =>
  useQuery({ queryKey: ['leadership', id], queryFn: () => api.getLeadership(id as number), enabled: id != null, staleTime: FIVE_MIN })

export const useStakeholder = (id: number | null) =>
  useQuery({ queryKey: ['stakeholder', id], queryFn: () => api.getStakeholder(id as number), enabled: id != null, staleTime: FIVE_MIN })

export const useLeadershipAnalysis = (id: number | null) =>
  useQuery({ queryKey: ['leadership-analysis', id], queryFn: () => api.getLeadershipAnalysis(id as number), enabled: id != null })

// ---- Metadata / facets ----
export const useFacets = () => useQuery({ queryKey: ['facets'], queryFn: api.getFacets, staleTime: FIVE_MIN })

export const useMetadata = (params: Parameters<typeof api.listMetadata>[0]) =>
  useQuery({ queryKey: ['metadata', params], queryFn: () => api.listMetadata(params), staleTime: FIVE_MIN })

// ---- Cohort compare ----
export const useCohortCompare = (params: { concept: string; group_by?: string; taxonomy?: string }, enabled = true) =>
  useQuery({ queryKey: ['cohort', params], queryFn: () => api.cohortCompare(params), enabled: enabled && !!params.concept, staleTime: FIVE_MIN })

// ---- Peer groups ----
export const usePeerGroups = () => useQuery({ queryKey: ['peer-groups'], queryFn: () => api.listPeerGroups(), staleTime: FIVE_MIN })
export const usePeerFactCompare = (id: number | null, concept: string) =>
  useQuery({ queryKey: ['peer-fact', id, concept], queryFn: () => api.peerFactCompare(id as number, concept), enabled: id != null && !!concept, staleTime: FIVE_MIN })

// ---- Macro ----
export const useSeriesBundles = () => useQuery({ queryKey: ['series-bundles'], queryFn: () => api.listSeriesBundles(), staleTime: FIVE_MIN })
/** A bundle's observations, transformed server-side the FRED way when `t` asks for it. */
export const useBundleObservations = (slug: string | null, t: api.SeriesTransformParams = {}) =>
  useQuery({
    queryKey: ['bundle-obs', slug, api.seriesTransformQuery(t)],
    queryFn: () => api.getBundleObservations(slug as string, 2000, t),
    enabled: !!slug,
    staleTime: FIVE_MIN,
  })

// ---- Mutations (admin) ----
export function useSyncSubmissions(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.syncSubmissions(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['filings'] })
      qc.invalidateQueries({ queryKey: ['sync-status', id] })
      qc.invalidateQueries({ queryKey: ['profile', id] })
    },
  })
}

export function useSyncFacts(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.syncFacts(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['facts'] })
      qc.invalidateQueries({ queryKey: ['statement', id] })
      qc.invalidateQueries({ queryKey: ['sync-status', id] })
      qc.invalidateQueries({ queryKey: ['profile', id] })
    },
  })
}

export function useComputeMetrics(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.computeMetrics(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['metrics', id] })
      qc.invalidateQueries({ queryKey: ['profile', id] })
    },
  })
}

export function useAnalyzeLeadership(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.analyzeLeadership(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leadership-analysis', id] }),
  })
}

export function useAddCompany() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { ticker?: string; cik?: string; name?: string }) => api.companyFromEdgar(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['companies'] })
      qc.invalidateQueries({ queryKey: ['metadata'] })
      qc.invalidateQueries({ queryKey: ['facets'] })
    },
  })
}
