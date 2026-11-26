import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import { ProtectedRoute, PublicOnlyRoute } from './components/RouteGuards'
import { FullPageLoader } from './components/ui'
import { usePageChrome } from './hooks/usePageChrome'
import AppLayout from './layouts/AppLayout'
import AuthLayout from './layouts/AuthLayout'
import Login from './pages/Login'
import Register from './pages/Register'

// Pages are loaded on demand, so charts (Recharts) only download when a page needs them.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Transactions = lazy(() => import('./pages/Transactions'))
const ExpenseForm = lazy(() => import('./pages/ExpenseForm'))
const IncomeForm = lazy(() => import('./pages/IncomeForm'))
const Review = lazy(() => import('./pages/Review'))
const Assistant = lazy(() => import('./pages/Assistant'))
const Report = lazy(() => import('./pages/Report'))
const Planned = lazy(() => import('./pages/Planned'))
const BudgetSetup = lazy(() => import('./pages/BudgetSetup'))
const Settings = lazy(() => import('./pages/Settings'))
const NotFound = lazy(() => import('./pages/NotFound'))

export default function App() {
  usePageChrome()
  const { pathname } = useLocation()
  return (
    <ErrorBoundary resetKey={pathname}>
      <Suspense fallback={<FullPageLoader />}>
        <Routes>
          <Route element={<PublicOnlyRoute />}>
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/transactions" element={<Transactions />} />
              <Route path="/expenses/new" element={<ExpenseForm />} />
              <Route path="/expenses/:id/edit" element={<ExpenseForm />} />
              <Route path="/income/new" element={<IncomeForm />} />
              <Route path="/income/:id/edit" element={<IncomeForm />} />
              <Route path="/review" element={<Review />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/report" element={<Report />} />
              {/* Recurring expenses now live on the dashboard. */}
              <Route path="/routines" element={<Navigate to="/dashboard#recurring" replace />} />
              <Route path="/planned" element={<Planned />} />
              <Route path="/budget" element={<BudgetSetup />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
