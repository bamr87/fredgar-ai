/** Display formatters for financial data — compact currency, ratios, dates, deltas. */

export function num(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/** Compact USD/large-number formatting: 1.23B, 45.6M, 12.3K. */
export function compact(v: number | string | null | undefined, opts?: { currency?: boolean }): string {
  const n = num(v)
  if (n === null) return '—'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  const cur = opts?.currency ? '$' : ''
  let out: string
  if (abs >= 1e12) out = `${(abs / 1e12).toFixed(2)}T`
  else if (abs >= 1e9) out = `${(abs / 1e9).toFixed(2)}B`
  else if (abs >= 1e6) out = `${(abs / 1e6).toFixed(2)}M`
  else if (abs >= 1e3) out = `${(abs / 1e3).toFixed(1)}K`
  else out = abs.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return `${sign}${cur}${out}`
}

export function money(v: number | string | null | undefined): string {
  return compact(v, { currency: true })
}

/** Full grouped integer (no compaction). */
export function fullNum(v: number | string | null | undefined): string {
  const n = num(v)
  if (n === null) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

/** Format a value using a unit hint (ratio / pct / usd / shares / EPS). */
export function byUnit(v: number | string | null | undefined, unit: string | null | undefined): string {
  const n = num(v)
  if (n === null) return '—'
  const u = (unit || '').toLowerCase()
  if (u === 'ratio') return n.toFixed(2)
  if (u === 'pct' || u === 'percent') return pct(n)
  if (u === 'usd/shares' || u.includes('/share')) {
    const sign = n < 0 ? '-' : ''
    return `${sign}$${Math.abs(n).toFixed(2)}`
  }
  if (u === 'usd' || u.includes('usd')) return money(n)
  return compact(n)
}

/** Full-precision label for hover tooltips (no compact suffixes). */
export function fullPrecision(v: number | string | null | undefined, unit?: string | null): string {
  const n = num(v)
  if (n === null) return ''
  const u = (unit || '').toLowerCase()
  if (u === 'usd/shares' || u.includes('/share')) {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }).format(n)
  }
  if (u === 'usd' || u.includes('usd')) {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(n)
  }
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

/** Human-readable unit tag (USD, USD/share). */
export function measureLabel(unit: string | null | undefined): string {
  if (!unit) return ''
  const u = unit.toLowerCase()
  if (u === 'usd/shares' || u.includes('/share')) return 'USD/share'
  if (u === 'usd' || u.includes('usd')) return 'USD'
  if (u === 'shares') return 'shares'
  if (u === 'pure' || u === 'number' || u === 'ratio' || u === 'pct' || u === 'percent') return ''
  return unit
}

/** Signed percent-points string: +2.0% / -1.4%. Input is already in percent units. */
export function signedPctPoints(v: number | null | undefined, digits = 1): string {
  const n = num(v)
  if (n === null) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(digits)}%`
}

export function pct(v: number | null | undefined, digits = 1): string {
  const n = num(v)
  if (n === null) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

/** Signed value with +/- prefix (for deltas, insider shares, orientation). */
export function signed(v: number | null | undefined, fmt: (n: number) => string = compact): string {
  const n = num(v)
  if (n === null) return '—'
  const s = fmt(Math.abs(n))
  return n > 0 ? `+${s}` : n < 0 ? `-${s}` : s
}

export function date(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v)
  if (isNaN(d.getTime())) return v
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function dateTime(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  if (isNaN(d.getTime())) return v
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** Relative time: "3 days ago", "just now". */
export function relTime(v: string | null | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  if (isNaN(d.getTime())) return v
  const diff = Date.now() - d.getTime()
  const min = Math.round(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.round(hr / 24)
  if (day < 30) return `${day}d ago`
  const mo = Math.round(day / 30)
  if (mo < 12) return `${mo}mo ago`
  return `${Math.round(mo / 12)}y ago`
}

/** A CIK left-padded to 10 digits, or the raw string. */
export function cik10(cik: string | null | undefined): string {
  if (!cik) return '—'
  const digits = cik.replace(/\D/g, '')
  return digits ? digits.padStart(10, '0') : cik
}

/** Strip leading zeros for SEC.gov URLs (which use the integer CIK). */
export function cikInt(cik: string): string {
  const n = parseInt(cik, 10)
  return Number.isFinite(n) ? String(n) : cik
}

export function secCompanyUrl(cik: string): string {
  return `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cikInt(cik)}&owner=exclude&count=40`
}

export function secFilingUrl(cik: string, accession: string): string {
  return `https://www.sec.gov/Archives/edgar/data/${cikInt(cik)}/${accession.replace(/-/g, '')}/`
}

/** Humanize a derived-metric / concept key: gross_margin -> Gross Margin. */
export function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** className composer (tiny clsx). */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}
