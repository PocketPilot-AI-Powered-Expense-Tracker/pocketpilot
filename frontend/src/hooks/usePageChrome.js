import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const TITLES = [
  ['/dashboard', 'Dashboard'], ['/transactions', 'Transactions'], ['/expenses/new', 'Add expense'],
  ['/expenses/', 'Edit expense'], ['/income/new', 'Add income'], ['/income/', 'Edit income'],
  ['/review', 'Review payments'], ['/assistant', 'AI assistant'], ['/planned', 'Planned expenses'],
  ['/report', 'Monthly report'], ['/budget', 'Budget'], ['/settings', 'Settings'],
  ['/login', 'Log in'], ['/register', 'Create account'],
]

/** Sets the browser tab title and scrolls to the top on every page change. */
export function usePageChrome() {
  const { pathname } = useLocation()
  useEffect(() => {
    const match = TITLES.find(([prefix]) => pathname.startsWith(prefix))
    document.title = match ? `${match[1]} · PocketPilot` : 'PocketPilot'
    if (!window.location.hash) window.scrollTo(0, 0)
  }, [pathname])
}
