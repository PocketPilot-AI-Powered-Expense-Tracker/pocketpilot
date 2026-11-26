import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { FullPageLoader } from './ui'

/** Only for signed-in users. New users without a budget are sent to setup first. */
export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullPageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!user.has_budget && location.pathname !== '/budget') return <Navigate to="/budget" replace />
  return <Outlet />
}

/** Login/register pages: bounce signed-in users to the dashboard. */
export function PublicOnlyRoute() {
  const { user, loading } = useAuth()
  if (loading) return <FullPageLoader />
  if (user) return <Navigate to={user.has_budget ? '/dashboard' : '/budget'} replace />
  return <Outlet />
}
