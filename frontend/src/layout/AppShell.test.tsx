import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AppProvider } from '../lib/app-context'
import { AppShell } from './AppShell'

// The shell's data hooks would call the API. Its landmarks do not depend on what
// they return, so stub them with settled answers and keep the test offline.
vi.mock('../lib/queries', () => ({
  useReady: () => ({ isPending: false, data: { status: 'ok' } }),
  useCompanies: () => ({ isPending: false, data: { results: [] } }),
}))

// What sequential focus navigation (Tab) stops on in this app.
const TABBABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function renderShell(path = '/companies') {
  return render(
    <AppProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route
              path="*"
              element={
                <div className="page">
                  <h1>Routed page</h1>
                  <button type="button">First page control</button>
                </div>
              }
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </AppProvider>,
  )
}

describe('AppShell landmarks (UPS-FE-11)', () => {
  it('makes a "Skip to content" link to #main-content the first Tab stop', () => {
    renderShell()
    const skip = screen.getByRole('link', { name: 'Skip to content' })
    expect(skip).toHaveAttribute('href', '#main-content')

    const tabbable = Array.from(document.querySelectorAll<HTMLElement>(TABBABLE))
    // No positive tabindex reorders Tab, so document order is the Tab order.
    expect(tabbable.some((el) => el.tabIndex > 0)).toBe(false)
    expect(tabbable[0]).toBe(skip)
  })

  it('renders exactly one main landmark, #main-content, around the routed page', () => {
    renderShell('/settings')
    const main = screen.getByRole('main') // throws if there is more than one
    expect(document.querySelectorAll('main')).toHaveLength(1)
    expect(main).toHaveAttribute('id', 'main-content')
    expect(within(main).getByRole('heading', { name: 'Routed page' })).toBeInTheDocument()

    // The sidebar nav and the top-bar search are what the skip link jumps past.
    expect(main).not.toContainElement(screen.getByRole('navigation'))
    expect(main).not.toContainElement(screen.getByRole('textbox', { name: 'Search companies' }))
  })

  it('points the skip link at a target that can take focus', () => {
    renderShell()
    const skip = screen.getByRole('link', { name: 'Skip to content' })
    const target = document.getElementById(skip.getAttribute('href')!.slice(1))
    expect(target).toBe(screen.getByRole('main'))

    // tabindex=-1: the browser focuses it when the link is followed, without
    // adding the whole content area to the Tab order.
    expect(target).toHaveAttribute('tabindex', '-1')
    target!.focus()
    expect(target).toHaveFocus()
  })
})
