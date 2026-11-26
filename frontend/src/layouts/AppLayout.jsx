import { BellRing, CalendarDays, FileText, LayoutDashboard, LogOut, Receipt, Settings, Sparkles, Wallet } from 'lucide-react'
import { Suspense } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { FullPageLoader, Logo } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { PendingProvider, usePendingCount } from '../context/PendingContext'

// New sections are added here as they are built.
const NAV = [
  { to: '/dashboard', label: 'Dashboard', short: 'Home', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', short: 'History', icon: Receipt },
  { to: '/review', label: 'Review payments', short: 'Review', icon: BellRing, badge: true },
  { to: '/assistant', label: 'AI assistant', short: 'Assistant', icon: Sparkles },
  { to: '/planned', label: 'Planned', short: 'Planned', icon: CalendarDays },
  { to: '/report', label: 'Monthly report', short: 'Report', icon: FileText, desktopOnly: true },
  { to: '/budget', label: 'Budget', short: 'Budget', icon: Wallet, desktopOnly: true },
  { to: '/settings', label: 'Settings', short: 'Settings', icon: Settings, desktopOnly: true },
]

function Badge({ n, className = '' }) {
  if (!n) return null
  return (
    <span className={`min-w-5 rounded-full bg-amber-500 px-1.5 text-center text-[11px] font-semibold leading-5 text-white ${className}`} aria-label={`${n} awaiting review`}>
      {n > 99 ? '99+' : n}
    </span>
  )
}

export default function AppLayout() {
  return (
    <PendingProvider>
      <Shell />
    </PendingProvider>
  )
}

function Shell() {
  const { count } = usePendingCount()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const onLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
    }`

  return (
    <div className="min-h-screen md:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 print:!hidden shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Logo className="mb-8 px-2" />
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, badge }) => (
            <NavLink key={to} to={to} className={linkClass}>
              <Icon className="h-4 w-4" /> <span className="flex-1">{label}</span> {badge && <Badge n={count} />}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 pt-4">
          <p className="truncate px-3 text-sm font-medium text-slate-800">{user?.name}</p>
          <p className="truncate px-3 text-xs text-slate-500">{user?.email}</p>
          <button onClick={onLogout} className="mt-3 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-10 flex print:hidden items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur md:hidden">
        <Logo />
        <div className="flex">
          <NavLink to="/settings" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label="Settings">
            <Settings className="h-5 w-5" />
          </NavLink>
          <button onClick={onLogout} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label="Log out">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      <main className="flex-1 px-4 pb-24 pt-6 md:px-8 md:pb-10">
        <div className="mx-auto max-w-5xl">
          {/* Inner Suspense keeps the sidebar visible while a page's code loads. */}
          <Suspense fallback={<FullPageLoader />}><Outlet /></Suspense>
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-10 flex print:hidden border-t border-slate-200 bg-white md:hidden">
        {NAV.filter((n) => !n.desktopOnly).map(({ to, short, icon: Icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `flex flex-1 flex-col items-center gap-1 py-2 text-xs ${isActive ? 'text-brand-700' : 'text-slate-500'}`}
          >
            <span className="relative">
              <Icon className="h-5 w-5" />
              {badge && <Badge n={count} className="absolute -right-3 -top-2" />}
            </span>
            {short}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
