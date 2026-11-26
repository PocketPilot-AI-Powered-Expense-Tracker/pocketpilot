import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Alert, Button, Field } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { getErrorMessage } from '../utils/errors'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    try {
      if (sessionStorage.getItem('pocketpilot_session_expired')) {
        setExpired(true)
        sessionStorage.removeItem('pocketpilot_session_expired')
      }
    } catch { /* storage unavailable */ }
  }, [])

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.email || !form.password) return setError('Please enter your email and password.')
    setLoading(true)
    try {
      const user = await login(form)
      navigate(user.has_budget ? location.state?.from || '/dashboard' : '/budget', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-500">Log in to see how much you can safely spend today.</p>
      </div>
      {expired && <Alert type="success">Your session expired for your security. Please log in again.</Alert>}
      <Alert>{error}</Alert>
      <Field id="email" label="Email" type="email" autoComplete="email" value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })} />
      <Field id="password" label="Password" type="password" autoComplete="current-password" value={form.password}
        onChange={(e) => setForm({ ...form, password: e.target.value })} />
      <Button type="submit" loading={loading} className="w-full">Log in</Button>
      <p className="text-center text-sm text-slate-500">
        New to PocketPilot? <Link to="/register" className="font-medium text-brand-700 hover:underline">Create an account</Link>
      </p>
    </form>
  )
}
