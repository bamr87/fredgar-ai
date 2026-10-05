import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cx } from '../../lib/format'

export type TabDef = { key: string; label: ReactNode; count?: number; icon?: ReactNode }

export function Tabs({ tabs, value, onChange }: { tabs: TabDef[]; value: string; onChange: (k: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const idx = Math.max(0, tabs.findIndex((t) => t.key === value))

  // WAI-ARIA tabs keyboard pattern: arrows move + activate, Home/End jump.
  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (tabs.length === 0) return
    let next: number
    if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length
    else if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = tabs.length - 1
    else return
    e.preventDefault()
    onChange(tabs[next].key)
    ref.current?.querySelectorAll<HTMLButtonElement>('button.tab')[next]?.focus()
  }

  return (
    <div className="tabs" role="tablist" ref={ref} onKeyDown={onKey}>
      {tabs.map((t) => {
        const active = value === t.key
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            className={cx('tab', active && 'active')}
            onClick={() => onChange(t.key)}
          >
            {t.icon}
            {t.label}
            {t.count != null && <span className="count">{t.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
