import { useLatestByConcepts } from '../../lib/queries'
import {
  HIGHLIGHT_CONCEPTS,
  HIGHLIGHT_KPIS,
  computeRatios,
  pickHighlights,
  toneClass,
} from '../../lib/finance'
import { byUnit, cx, date, fullPrecision, measureLabel } from '../../lib/format'
import { Card, CardHeader, EmptyState, Query } from '../../components/ui'

export function KpiHighlights({ id }: { id: number }) {
  const latest = useLatestByConcepts(id, HIGHLIGHT_CONCEPTS)
  return (
    <Card>
      <CardHeader
        title="Financial highlights"
        sub="Latest warehouse XBRL facts — compact values, hover for full precision"
      />
      <Query
        q={latest}
        isEmpty={(d) => Object.values(pickHighlights(d.values)).every((row) => !row)}
        empty={<EmptyState title="No financial highlights" message="Sync facts to populate latest XBRL values." />}
      >
        {(d) => {
          const picked = pickHighlights(d.values)
          const ratios = computeRatios(picked)
          return (
            <>
              <div
                className="card-body"
                style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(10.5rem, 1fr))', gap: 'var(--sp-3)' }}
              >
                {HIGHLIGHT_KPIS.map((spec) => {
                  const row = picked[spec.key]
                  const n = row?.value ?? null
                  return (
                    <div key={spec.key} className="stat" style={{ padding: 'var(--sp-2)' }}>
                      <div className="stat-label">{spec.label}</div>
                      <div
                        className={cx('stat-value', n != null && n < 0 && 'neg')}
                        style={{ fontSize: 'var(--fs-lg)' }}
                        title={row ? fullPrecision(row.value, row.unit) : undefined}
                      >
                        {row ? byUnit(row.value, row.unit) : '—'}
                      </div>
                      <div className="stat-sub">
                        {row?.unit ? <span className="badge">{measureLabel(row.unit) || row.unit}</span> : null}
                        {row?.period_end ? ` ${date(row.period_end)}` : ''}
                      </div>
                    </div>
                  )
                })}
              </div>
              {ratios.length > 0 && (
                <div className="card-body" style={{ borderTop: '1px solid var(--c-border)' }}>
                  <div className="caption" style={{ marginBottom: 'var(--sp-3)' }}>
                    Derived ratios from the highlights above (latest fact per concept, so input periods can differ)
                  </div>
                  <div className="row gap-3 wrap">
                    {ratios.map((r) => (
                      <div key={r.key} className="stat" style={{ padding: 'var(--sp-2)', minWidth: '7.5rem' }}>
                        <div className="stat-label">{r.label}</div>
                        <div className={cx('stat-value', r.signed && toneClass(r.value > 0 ? 1 : r.value < 0 ? -1 : 0))} style={{ fontSize: 'var(--fs-lg)' }}>
                          {r.display}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )
        }}
      </Query>
    </Card>
  )
}
