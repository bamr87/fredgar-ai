/** Application chrome: skip link, sidebar navigation + sticky top bar with global
 *  search, theme toggle, backend-readiness indicator, and admin status, around
 *  the page's one main landmark (`#main-content`), which holds the routed page. */
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useApp } from '../lib/app-context'
import { useReady } from '../lib/queries'
import { cx } from '../lib/format'
import { CompanySearch } from '../components/CompanySearch'
import {
  IconBuilding,
  IconCompare,
  IconDashboard,
  IconGlobe,
  IconGroup,
  IconMenu,
  IconMoon,
  IconSearch,
  IconSettings,
  IconSun,
} from '../components/ui/icons'

// Public, read-only static mirror of the warehouse (GitHub Pages). Optional —
// the link renders only when the deployment sets VITE_STATIC_SITE_URL.
const STATIC_SITE_URL = import.meta.env.VITE_STATIC_SITE_URL?.replace(/\/$/, '') || ''

const NAV = [
  { group: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: <IconDashboard />, end: true }] },
  {
    group: 'Explore',
    items: [
      { to: '/companies', label: 'Companies', icon: <IconBuilding /> },
      { to: '/search', label: 'Filing Search', icon: <IconSearch /> },
      { to: '/compare', label: 'Compare', icon: <IconCompare /> },
      { to: '/peers', label: 'Peer Groups', icon: <IconGroup /> },
      { to: '/macro', label: 'Macro Series', icon: <IconGlobe /> },
    ],
  },
]

function ThemeToggle() {
  const { theme, setTheme } = useApp()
  const isDark = theme === 'dark'
  return (
    <button className="btn btn-icon btn-ghost" title={`Theme: ${theme}`} onClick={() => setTheme(isDark ? 'light' : 'dark')} aria-label="Toggle theme">
      {isDark ? <IconSun width={18} height={18} /> : <IconMoon width={18} height={18} />}
    </button>
  )
}

function ReadyDot() {
  const ready = useReady()
  const ok = ready.data?.status === 'ok'
  const color = ready.isPending ? 'var(--c-text-subtle)' : ok ? 'var(--c-positive)' : 'var(--c-negative)'
  return (
    <span className="provenance" title={ok ? 'Backend healthy' : 'Backend unreachable'}>
      <span className="dot" style={{ color }} />
      <span className="hide-sm">{ready.isPending ? 'Checking…' : ok ? 'API online' : 'API offline'}</span>
    </span>
  )
}

export function AppShell() {
  const { isAdmin } = useApp()
  const [menuOpen, setMenuOpen] = useState(false)

  // Cmd/Ctrl+K focuses the global company search — unless the user is already
  // typing in a field, so the shortcut never steals focus mid-edit.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        const el = document.activeElement as HTMLElement | null
        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) return
        e.preventDefault()
        document.querySelector<HTMLInputElement>('.topbar input')?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="shell">
      {/* First focusable element on every route (UPS-FE-11): keyboard and
          screen-reader users jump past the sidebar nav and the top bar. */}
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className={cx('scrim', menuOpen && 'show')} onClick={() => setMenuOpen(false)} />
      <aside className={cx('sidebar', menuOpen && 'open')}>
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <div className="brand-name">Fredgar AI</div>
            <div className="brand-sub">Company &amp; macro intelligence</div>
          </div>
        </div>
        <nav onClick={() => setMenuOpen(false)}>
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="nav-group-label">{g.group}</div>
              {g.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={(it as { end?: boolean }).end} className={({ isActive }) => cx('nav-item', isActive && 'active')}>
                  {it.icon}
                  {it.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          {STATIC_SITE_URL && (
            <a className="nav-item" href={`${STATIC_SITE_URL}/`} target="_blank" rel="noreferrer" title="Static, no-login mirror of this data">
              <IconGlobe />
              Public mirror ↗
            </a>
          )}
          <NavLink to="/settings" className={({ isActive }) => cx('nav-item', isActive && 'active')} onClick={() => setMenuOpen(false)}>
            <IconSettings />
            Settings
            {isAdmin && <span className="badge badge-pos" style={{ marginLeft: 'auto' }}>admin</span>}
          </NavLink>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="btn btn-icon btn-ghost menu-btn" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <IconMenu width={18} height={18} />
          </button>
          <div style={{ maxWidth: 460 }} className="grow">
            <CompanySearch kbd />
          </div>
          <div className="row gap-3" style={{ marginLeft: 'auto' }}>
            <ReadyDot />
            <ThemeToggle />
          </div>
        </header>
        {/* tabIndex -1: following the skip link focuses the page content
            without adding the whole area to the Tab order. */}
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
