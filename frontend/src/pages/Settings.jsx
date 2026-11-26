import { LogOut, Repeat, Sparkles, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { aiService } from '../services/aiService'
import { Link, useNavigate } from 'react-router-dom'
import Modal from '../components/Modal'
import { Alert, Button, Card, Field } from '../components/ui'
import { getErrorMessage } from '../utils/errors'
import { useAuth } from '../context/AuthContext'

export default function Settings() {
  const { user, logout, deleteAccount } = useAuth()
  const [deleting, setDeleting] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [busy, setBusy] = useState(false)
  const doDelete = async () => {
    setBusy(true)
    setDeleteError('')
    try {
      await deleteAccount()
      navigate('/register', { replace: true })
    } catch (err) {
      setDeleteError(getErrorMessage(err))
      setBusy(false)
    }
  }
  const navigate = useNavigate()
  const [ai, setAi] = useState(null)
  useEffect(() => { aiService.status().then(setAi).catch(() => setAi({ ai_available: false })) }, [])
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
      <Card>
        <h2 className="font-medium text-slate-800">Profile</h2>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-slate-500">Name</dt><dd className="font-medium">{user?.name}</dd></div>
          <div><dt className="text-slate-500">Email</dt><dd className="font-medium">{user?.email}</dd></div>
          <div><dt className="text-slate-500">Member since</dt><dd className="font-medium">{user && new Date(user.created_at).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</dd></div>
          <div><dt className="text-slate-500">Currency</dt><dd className="font-medium">Indian Rupee (₹)</dd></div>
        </dl>
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-slate-800">Budget</h2>
          <p className="text-sm text-slate-500">Change your allowance, income, savings target or budget start day.</p>
        </div>
        <Link to="/budget"><Button variant="secondary">Edit budget</Button></Link>
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-slate-800">Recurring expenses</h2>
          <p className="text-sm text-slate-500">Rent, subscriptions and daily habits. Managed on your dashboard.</p>
        </div>
        <Link to="/dashboard#recurring"><Button variant="secondary"><Repeat className="h-4 w-4" /> Manage</Button></Link>
      </Card>
      <Card>
        <h2 className="flex items-center gap-2 font-medium text-slate-800"><Sparkles className="h-4 w-4 text-violet-600" /> AI features</h2>
        <p className="mt-1 text-sm text-slate-500">
          {ai === null ? 'Checking…' : ai.ai_available
            ? `${({ groq: 'Groq', gemini: 'Gemini' })[ai.provider] || 'AI'} is connected. It explains numbers PocketPilot calculates and never changes your data without your confirmation. Only totals and category names are shared with it.`
            : 'AI is not configured (no API key on the server). The assistant, insights and report use built-in rules instead.'}
        </p>
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-slate-800">Log out</h2>
          <p className="text-sm text-slate-500">You'll need your email and password to sign in again.</p>
        </div>
        <Button variant="danger" onClick={() => { logout(); navigate('/login', { replace: true }) }}>
          <LogOut className="h-4 w-4" /> Log out
        </Button>
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-3 ring-rose-200">
        <div>
          <h2 className="font-medium text-rose-700">Delete account</h2>
          <p className="text-sm text-slate-500">Permanently delete your account and all your expenses, income, recurring expenses and reviews.</p>
        </div>
        <Button variant="secondary" className="text-rose-700" onClick={() => { setConfirmText(''); setDeleting(true) }}>
          <Trash2 className="h-4 w-4" /> Delete account
        </Button>
      </Card>
      <Modal open={deleting} title="Delete your account?" onClose={() => setDeleting(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setDeleting(false)}>Cancel</Button>
          <Button variant="danger" loading={busy} disabled={confirmText !== 'DELETE'} onClick={doDelete}>Delete everything</Button>
        </>}>
        <div className="space-y-3">
          <p className="text-sm text-slate-600">This removes all your PocketPilot data and cannot be undone. Type <b>DELETE</b> to confirm.</p>
          <Field id="confirm-delete" label="Confirmation" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoComplete="off" />
          <Alert>{deleteError}</Alert>
        </div>
      </Modal>
    </div>
  )
}
