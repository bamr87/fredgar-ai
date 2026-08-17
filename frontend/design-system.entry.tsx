/* eslint-disable react-refresh/only-export-components -- this barrel is not part
   of the app's module graph, so Fast Refresh boundaries do not apply to it. */
/**
 * Design-system entry point for /design-sync (claude.ai/design).
 *
 * The app itself never imports this file — Vite builds from `index.html` →
 * `src/main.tsx`, and `tsconfig.app.json` only includes `src/`, so nothing here
 * affects `npm run build`. It exists to give the component library one explicit
 * export surface for the converter to bundle, since this package ships no
 * library `dist/`.
 *
 * See `.design-sync/NOTES.md` for why this lives at the package root.
 */
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AppProvider } from './src/lib/app-context'

// ---- The component library ----
export * from './src/components/ui'
export * from './src/components/ui/Chart'
export * from './src/components/CompanySearch'
export * from './src/components/CompanyMultiSelect'
export * from './src/components/ErrorBoundary'
export * from './src/components/PageHeader'
export * from './src/components/Pager'
export * from './src/layout/AppShell'
export * from './src/lib/toast'

// `ErrorState` branches on `instanceof ApiError`, so the class has to be
// reachable for that state to be renderable. Excluded from the card index via
// cfg.componentSrcMap — it is API, not a component.
export { ApiError } from './src/lib/http'

// ---- Preview / design-time provider ----
// Router + TanStack Query + app state, so the data-aware components
// (AppShell, CompanySearch, CompanyMultiSelect) mount outside the real app.
const previewClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false, staleTime: Infinity },
  },
})
previewClient.setQueryData(['ready'], { status: 'ok' })

/**
 * Wraps children in the contexts the app normally provides. Every preview card
 * renders inside this; components that read no context are unaffected.
 */
export function DesignSystemProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={previewClient}>
      <MemoryRouter>
        <AppProvider>{children}</AppProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}
