import { Outlet } from 'react-router-dom'
import { Logo } from '../components/ui'

export default function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-brand-50 via-white to-sky-50 px-4 py-10">
      <Logo className="mb-6 text-xl" />
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lg ring-1 ring-slate-200 sm:p-8">
        <Outlet />
      </div>
      <p className="mt-6 max-w-sm text-center text-xs text-slate-500">Plan your spending, not just track it.</p>
    </div>
  )
}
