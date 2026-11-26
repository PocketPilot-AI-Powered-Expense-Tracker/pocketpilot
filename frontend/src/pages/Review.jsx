import { Ban, Check, CheckCircle2, Clock, Hourglass, Inbox, Pencil, RotateCcw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CategoryIcon } from '../components/CategoryBadge'
import Modal from '../components/Modal'
import NotificationSimulator from '../components/NotificationSimulator'
import { Alert, Button, Card, EmptyState, Field, FullPageLoader, PageHeader, Select, TextArea } from '../components/ui'
import { usePendingCount } from '../context/PendingContext'
import { useAsync } from '../hooks/useAsync'
import { pendingService } from '../services/pendingService'
import { CATEGORIES, PAYMENT_METHODS, categoryMeta } from '../utils/constants'
import { todayISO, toISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { formatINR, paiseToRupeesInput, rupeesToPaise } from '../utils/money'
import { sourceApp } from '../utils/upiSamples'

const TABS = [
  { key: 'pending_review', label: 'Awaiting review' },
  { key: 'accepted', label: 'Added' },
  { key: 'rejected', label: 'Rejected' },
]

const fmtWhen = (iso) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })

function AppChip({ app }) {
  const a = sourceApp(app)
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${a.cls}`}>{a.label}</span>
}

function PendingCard({ t, onAccept, onEdit, onReject, busy }) {
  const [category, setCategory] = useState(t.suggested_category)
  return (
    <li className="rounded-2xl border-2 border-dashed border-amber-300 bg-amber-50/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
            <Hourglass className="h-3 w-3" /> Awaiting review · not in your expenses yet
          </span>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{formatINR(t.amount_paise)}</p>
          <p className="truncate text-sm text-slate-700">{t.counterparty ? <>to <span className="font-medium">{t.counterparty}</span></> : 'Recipient not shown in notification'}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <AppChip app={t.source_app} />
            <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" /> {fmtWhen(t.detected_at)}</span>
            {t.ref_last4 && <span>Ref ••••{t.ref_last4}</span>}
            {t.origin === 'simulator' && <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-600">Sample</span>}
          </p>
        </div>
        <div className="w-full sm:w-60">
          <Select id={`cat-${t.id}`} label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}{c.value === t.suggested_category ? ' (suggested)' : ''}</option>)}
          </Select>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={() => onAccept(t, category)} disabled={busy}><Check className="h-4 w-4" /> Add to Expenses</Button>
        <Button variant="secondary" onClick={() => onEdit(t, category)} disabled={busy}><Pencil className="h-4 w-4" /> Edit</Button>
        <Button variant="secondary" onClick={() => onReject(t)} disabled={busy} className="text-rose-700"><Ban className="h-4 w-4" /> Reject</Button>
      </div>
    </li>
  )
}

function ReviewedRow({ t, onRestore, busy }) {
  const accepted = t.status === 'accepted'
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      {accepted ? <CategoryIcon category={t.suggested_category} /> : (
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-400"><XCircle className="h-4 w-4" /></span>
      )}
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm font-medium ${accepted ? 'text-slate-800' : 'text-slate-500'}`}>{t.counterparty || `${sourceApp(t.source_app).label} payment`}</p>
        <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <AppChip app={t.source_app} /> <span>{fmtWhen(t.detected_at)}</span>
          {accepted
            ? <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 ring-1 ring-emerald-200"><CheckCircle2 className="h-3 w-3" /> Added to expenses</span>
            : <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600 ring-1 ring-slate-200">Rejected · not counted</span>}
        </p>
      </div>
      <span className={`text-sm font-semibold ${accepted ? 'text-slate-900' : 'text-slate-400 line-through'}`}>{formatINR(t.amount_paise)}</span>
      {accepted && t.expense_id && <Link to={`/expenses/${t.expense_id}/edit`} className="text-xs font-medium text-brand-700 hover:underline">View expense</Link>}
      {!accepted && <Button variant="secondary" className="px-2.5 py-1.5 text-xs" onClick={() => onRestore(t)} disabled={busy}><RotateCcw className="h-3.5 w-3.5" /> Restore</Button>}
    </li>
  )
}

export default function Review() {
  const [params, setParams] = useSearchParams()
  const tab = TABS.some((t) => t.key === params.get('tab')) ? params.get('tab') : 'pending_review'
  const { refresh: refreshBadge } = usePendingCount()
  const { data, error, loading, reload } = useAsync(() => pendingService.list(tab), [tab])
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState(null) // { text, undo? }
  const [actionError, setActionError] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({})
  const [formError, setFormError] = useState('')

  useEffect(() => { refreshBadge() }, [data, refreshBadge])

  const after = async (msg) => {
    setFlash(msg)
    await reload({ silent: true })
  }

  const accept = async (t, category, overrides = {}) => {
    setBusy(true)
    setActionError('')
    try {
      await pendingService.accept(t.id, { category, ...overrides })
      setEditing(null)
      await after({ text: `${formatINR(overrides.amount_paise || t.amount_paise)} added to your expenses as ${categoryMeta(overrides.category || category).label}.` })
    } catch (err) {
      if (editing) setFormError(getErrorMessage(err))
      else setActionError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const reject = async (t) => {
    setBusy(true)
    setActionError('')
    try {
      await pendingService.reject(t.id)
      await after({ text: `Rejected ${formatINR(t.amount_paise)}${t.counterparty ? ` to ${t.counterparty}` : ''}. It won't count in your budget.`, undo: t })
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const restore = async (t) => {
    setBusy(true)
    try {
      await pendingService.restore(t.id)
      await after({ text: 'Moved back to "Awaiting review".' })
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const openEdit = (t, category) => {
    const detectedDay = toISO(new Date(t.detected_at))
    setFormError('')
    setForm({ amount: paiseToRupeesInput(t.amount_paise), description: t.counterparty || `${sourceApp(t.source_app).label} payment`,
      category, date: detectedDay > todayISO() ? todayISO() : detectedDay, payment_method: 'upi', notes: '' })
    setEditing(t)
  }

  const submitEdit = (e) => {
    e.preventDefault()
    const amount = rupeesToPaise(form.amount)
    if (!amount) return setFormError('Enter an amount greater than ₹0.')
    if (!form.description.trim()) return setFormError('Add a short description.')
    if (!form.date || form.date > todayISO()) return setFormError('Pick today or an earlier date.')
    accept(editing, form.category, { amount_paise: amount, category: form.category, description: form.description.trim(),
      date: form.date, payment_method: form.payment_method, notes: form.notes.trim() || null })
  }

  const items = data?.items || []
  const counts = data?.counts || {}

  return (
    <div>
      <PageHeader title="Review detected payments"
        subtitle="Payments spotted from UPI notifications. They only count in your budget after you add them, so transfers to friends or family can be rejected." />

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div>
          <div className="mb-4 inline-flex rounded-lg bg-slate-100 p-1" role="tablist">
            {TABS.map((t) => (
              <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setParams({ tab: t.key })}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${tab === t.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'}`}>
                {t.label}{counts[t.key] ? <span className={`ml-1.5 rounded-full px-1.5 text-xs ${t.key === 'pending_review' ? 'bg-amber-200 text-amber-900' : 'bg-slate-200 text-slate-700'}`}>{counts[t.key]}</span> : null}
              </button>
            ))}
          </div>

          <div className="mb-3 space-y-2">
            {flash && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800 ring-1 ring-emerald-200" role="status">
                <span>{flash.text}</span>
                {flash.undo && <button className="font-semibold underline" onClick={() => restore(flash.undo)} disabled={busy}>Undo</button>}
              </div>
            )}
            <Alert>{actionError}</Alert>
          </div>

          {loading ? <FullPageLoader /> : error ? (
            <div className="space-y-3"><Alert>{error}</Alert><Button variant="secondary" onClick={() => reload()}>Try again</Button></div>
          ) : items.length === 0 ? (
            <Card>
              <EmptyState icon={Inbox} title={tab === 'pending_review' ? 'All caught up' : tab === 'accepted' ? 'Nothing added yet' : 'Nothing rejected'}>
                {tab === 'pending_review' ? 'No detected payments are waiting. Try the notification simulator to see how it works.' : 'Reviewed payments will show up here.'}
              </EmptyState>
            </Card>
          ) : tab === 'pending_review' ? (
            <ul className="space-y-3">
              {items.map((t) => <PendingCard key={t.id} t={t} busy={busy} onAccept={accept} onEdit={openEdit} onReject={reject} />)}
            </ul>
          ) : (
            <Card><ul className="divide-y divide-slate-100">{items.map((t) => <ReviewedRow key={t.id} t={t} busy={busy} onRestore={restore} />)}</ul></Card>
          )}
        </div>

        <div className="space-y-4">
          <NotificationSimulator onCreated={() => { if (tab === 'pending_review') reload({ silent: true }); else refreshBadge() }} />
          <Card className="text-sm text-slate-600">
            <p className="font-medium text-slate-800">How this works</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              <li>A payment notification is detected.</li>
              <li>It appears here as <span className="font-medium text-amber-800">Awaiting review</span>.</li>
              <li><span className="font-medium">Add</span> it if it was your spending, or <span className="font-medium">Reject</span> it (e.g. money sent to family).</li>
              <li>Only added payments change your budget. Each one is added exactly once.</li>
            </ol>
          </Card>
        </div>
      </div>

      <Modal open={Boolean(editing)} title="Edit and add to expenses" onClose={() => setEditing(null)}>
        {editing && (
          <form onSubmit={submitEdit} noValidate className="space-y-4">
            <Alert>{formError}</Alert>
            <p className="text-xs text-slate-500">Detected: {formatINR(editing.amount_paise)} via {sourceApp(editing.source_app).label} on {fmtWhen(editing.detected_at)}. Fix anything that's wrong, e.g. only your share of a split bill.</p>
            <Field id="e-amount" label="Amount" prefix="₹" inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <Field id="e-desc" label="Description" maxLength={120} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Select id="e-cat" label="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </Select>
              <Field id="e-date" label="Date" type="date" max={todayISO()} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </div>
            <Select id="e-pay" label="Paid with" value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
              {PAYMENT_METHODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </Select>
            <TextArea id="e-notes" label="Notes (optional)" maxLength={500} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
              <Button type="submit" loading={busy}><Check className="h-4 w-4" /> Save and add</Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
