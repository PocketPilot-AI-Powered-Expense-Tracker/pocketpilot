import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Field } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { getErrorMessage } from '../utils/errors'

function validate({ name, email, password, confirm }) {
  const errors = {}
  if (!name.trim()) errors.name = 'Please enter your name.'
  if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = 'Enter a valid email address.'
  if (password.length < 8) errors.password = 'Use at least 8 characters.'
  else if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) errors.password = 'Include at least one letter and one number.'
  if (confirm !== password) errors.confirm = 'Passwords do not match.'
  return errors
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setServerError('')
    const v = validate(form)
    setErrors(v)
    if (Object.keys(v).length) return
    setLoading(true)
    try {
      await register({ name: form.name.trim(), email: form.email.trim(), password: form.password })
      navigate('/budget', { replace: true })
    } catch (err) {
      setServerError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">Takes a minute. Next, you'll set up your monthly budget.</p>
      </div>
      <Alert>{serverError}</Alert>
      <Field id="name" label="Name" autoComplete="name" value={form.name} onChange={set('name')} error={errors.name} />
      <Field id="email" label="Email" type="email" autoComplete="email" value={form.email} onChange={set('email')} error={errors.email} />
      <Field id="password" label="Password" type="password" autoComplete="new-password" value={form.password}
        onChange={set('password')} error={errors.password} hint="At least 8 characters, with a letter and a number." />
      <Field id="confirm" label="Confirm password" type="password" autoComplete="new-password" value={form.confirm}
        onChange={set('confirm')} error={errors.confirm} />
      <Button type="submit" loading={loading} className="w-full">Create account</Button>
      <p className="text-center text-sm text-slate-500">
        Already have an account? <Link to="/login" className="font-medium text-brand-700 hover:underline">Log in</Link>
      </p>
    </form>
  )
}
