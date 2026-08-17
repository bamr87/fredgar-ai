import { AppShell } from 'frontend'

// AppShell is the whole application chrome — sidebar nav, sticky top bar with
// global search, readiness indicator, and theme toggle — with an <Outlet/> for
// the routed page. The router and query client come from DesignSystemProvider,
// which wraps every preview.
//
// The content area is intentionally empty: nesting <Routes> here renders
// nothing, because a preview-side `react-router-dom` import is a second copy of
// the library and does not share context with the router bundled into
// _ds_bundle.js. The chrome is what this component owns, and that is what the
// card shows.
export const FullChrome = () => <AppShell />
