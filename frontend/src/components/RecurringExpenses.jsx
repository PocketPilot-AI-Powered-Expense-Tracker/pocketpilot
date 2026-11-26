import { CalendarClock, Pause, Pencil, Play, Plus, Repeat, Trash2, Zap, Hand } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '../hooks/useAsync'
import { routineService } from '../services/routineService'
import { CATEGORIES, PAYMENT_METHODS, WEEKDAYS } from '../utils/constants'
import { fmtDate, toISO, todayISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { formatINR, paiseToRupeesInput, rupeesToPaise } from '../utils/money'
import { describeSchedule } from '../utils/routines'
import { CategoryIcon } from './CategoryBadge'
import Modal, { ConfirmDialog } from './Modal'
import { Alert, Button, Card, EmptyState, Field, Select } from './ui'

const EXAMPLES = [
  { name: 'Room rent', amount: '6000', category: 'rent', frequency: 'monthly', day_of_month: '1', deduction_mode: 'auto' },
  { name: 'Tea', amount: '30', category: 'food', frequency: 'daily', deduction_mode: 'manual' },
  { name: 'Outside food', amount: '200', category: 'food', frequency: 'weekly', weekday: '6', deduction_mode: 'manual' },
  { name: 'Spotify', amount: '119', category: 'subscriptions', frequency: 'monthly', day_of_month: '10', deduction_mode: 'auto' },
  { name: 'Bus pass', amount: '500', category: 'transportation', frequency: 'weekly', weekday: '0', deduction_mode: 'manual' },
]

const MODES = [
  { value: 'auto', icon: Zap, title: 'Deduct automatically',
    text: 'Recorded as an expense on each due date until you change it. Best for rent, subscriptions and fees.' },
  { value: 'manual', icon: Hand, title: 'Deduct when I tap',
    text: 'Money is kept aside, and you tap "Spent" when it happens. Best for tea, snacks or outings.' },
]

const blank = () => ({ name: '', amount: '', category: 'food', frequency: 'daily', weekday: '6', day_of_month: '1',
  start_date: todayISO(), end_date: '', payment_method: 'upi', deduction_mode: 'manual' })

export function ModeBadge({ mode }) {
  return mode === 'auto' ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700 ring-1 ring-violet-200">
      <Zap className="h-3 w-3" /> Auto-deduct
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-sky-200">
      <Hand className="h-3 w-3" /> Tap to record
    </span>
  )
}

export function RecurringForm({ initial, onSaved, onCancel }) {
  const isEdit = Boolean(initial?.id)
  const [form, setForm] = useState(() => initial?.id ? {
    name: initial.name, amount: paiseToRupeesInput(initial.amount_paise), category: initial.category,
    frequency: initial.frequency, weekday: String(initial.weekday ?? 6), day_of_month: String(initial.day_of_month ?? 1),
    start_date: initial.start_date, end_date: initial.end_date || '', payment_method: initial.payment_method,
    deduction_mode: initial.deduction_mode || 'manual',
  } : { ...blank(), ...(initial || {}) })
  const [modeTouched, setModeTouched] = useState(isEdit)
  const [deductThisMonth, setDeductThisMonth] = useState(false) // answer: default "No"
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  // Sensible default: rent & subscriptions are usually automatic, until the user picks a mode.
  const setCategory = (e) => {
    const category = e.target.value
    setForm({ ...form, category, ...(modeTouched ? {} : { deduction_mode: ['rent', 'subscriptions'].includes(category) ? 'auto' : 'manual' }) })
  }

  // "Deduct for this month too?" — only when adding a MONTHLY expense whose due day this
  // month has already passed and the start date would otherwise skip it.
  const now = new Date()
  const domNum = Number(form.day_of_month)
  const dueThisMonth = form.frequency === 'monthly' && Number.isInteger(domNum) && domNum >= 1 && domNum < now.getDate()
    ? toISO(new Date(now.getFullYear(), now.getMonth(), domNum)) : null
  const nextDue = dueThisMonth ? toISO(new Date(now.getFullYear(), now.getMonth() + 1, domNum)) : null
  const offerThisMonth = !isEdit && dueThisMonth && form.start_date > dueThisMonth && (!form.end_date || form.end_date >= dueThisMonth)
  const monthName = now.toLocaleString('en-IN', { month: 'long' })
  const amountPreview = rupeesToPaise(form.amount)

  const submit = async (e) => {
    e.preventDefault()
    setServerError('')
    const amount = rupeesToPaise(form.amount)
    const dom = Number(form.day_of_month)
    const v = {}
    if (!form.name.trim()) v.name = 'Give it a name, e.g. "Room rent" or "Tea".'
    if (!amount) v.amount = 'Enter an amount greater than ₹0.'
    if (form.frequency === 'monthly' && !(Number.isInteger(dom) && dom >= 1 && dom <= 28)) v.day_of_month = 'Pick a day from 1 to 28.'
    if (!form.start_date) v.start_date = 'Pick a start date.'
    if (form.end_date && form.end_date < form.start_date) v.end_date = 'End date must be after the start date.'
    setErrors(v)
    if (Object.keys(v).length) return
    const payload = {
      name: form.name.trim(), amount_paise: amount, category: form.category, frequency: form.frequency,
      weekday: form.frequency === 'weekly' ? Number(form.weekday) : null,
      day_of_month: form.frequency === 'monthly' ? dom : null,
      start_date: form.start_date, end_date: form.end_date || null, payment_method: form.payment_method,
      deduction_mode: form.deduction_mode,
      deduct_this_month: Boolean(offerThisMonth && deductThisMonth),
    }
    setSaving(true)
    try {
      const saved = isEdit ? await routineService.update(initial.id, payload) : await routineService.create(payload)
      onSaved(saved, isEdit)
    } catch (err) {
      setServerError(getErrorMessage(err))
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <Alert>{serverError}</Alert>
      {!isEdit && (
        <div className="flex flex-wrap gap-1.5">
          <span className="w-full text-xs text-slate-500">Quick start:</span>
          {EXAMPLES.map((ex) => (
            <button type="button" key={ex.name} onClick={() => { setForm({ ...blank(), ...ex }); setModeTouched(true) }}
              className="rounded-full px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50">
              {ex.name} ₹{Number(ex.amount).toLocaleString('en-IN')}
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="r-name" label="Name" placeholder="Room rent" maxLength={60} value={form.name} onChange={set('name')} error={errors.name} />
        <Field id="r-amount" label="Amount each time" prefix="₹" inputMode="decimal" placeholder="6000" value={form.amount} onChange={set('amount')} error={errors.amount} />
      </div>
      <Select id="r-category" label="Category" value={form.category} onChange={setCategory}>
        {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </Select>
      <div>
        <span className="mb-1.5 block text-sm font-medium text-slate-700">How often?</span>
        <div className="inline-flex rounded-lg bg-slate-100 p-1" role="radiogroup" aria-label="Frequency">
          {['daily', 'weekly', 'monthly'].map((f) => (
            <button type="button" key={f} role="radio" aria-checked={form.frequency === f} onClick={() => setForm({ ...form, frequency: f })}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${form.frequency === f ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>
      {form.frequency === 'weekly' && (
        <Select id="r-weekday" label="Every" value={form.weekday} onChange={set('weekday')}>
          {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
        </Select>
      )}
      {form.frequency === 'monthly' && (
        <Field id="r-dom" label="Day of the month" type="number" min={1} max={28} value={form.day_of_month} onChange={set('day_of_month')} error={errors.day_of_month} />
      )}

      <div>
        <span className="mb-1.5 block text-sm font-medium text-slate-700">How should it be deducted?</span>
        <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Deduction mode">
          {MODES.map(({ value, icon: Icon, title, text }) => (
            <button type="button" key={value} role="radio" aria-checked={form.deduction_mode === value}
              onClick={() => { setForm({ ...form, deduction_mode: value }); setModeTouched(true) }}
              className={`rounded-xl border p-3 text-left transition ${form.deduction_mode === value ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500' : 'border-slate-200 hover:bg-slate-50'}`}>
              <span className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Icon className="h-4 w-4 text-brand-700" /> {title}</span>
              <span className="mt-1 block text-xs text-slate-600">{text}</span>
            </button>
          ))}
        </div>
      </div>

      {offerThisMonth && (
        <div className="rounded-xl bg-amber-50 p-3 ring-1 ring-amber-200">
          <p className="text-sm font-medium text-amber-900">
            This month's due date ({fmtDate(dueThisMonth)}) has already passed.
          </p>
          <p className="mt-0.5 text-xs text-amber-800">Should PocketPilot also deduct it for {monthName}?</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label={`Deduct for ${monthName}`}>
            {[
              { value: false, title: `No, start from ${fmtDate(nextDue)}`, text: `Nothing is recorded for ${monthName}.` },
              { value: true, title: `Yes, deduct for ${monthName}`, text: `${amountPreview ? formatINR(amountPreview) : 'The amount'} is recorded now, dated ${fmtDate(dueThisMonth)}.` },
            ].map((o) => (
              <button type="button" key={String(o.value)} role="radio" aria-checked={deductThisMonth === o.value}
                onClick={() => setDeductThisMonth(o.value)}
                className={`rounded-lg border bg-white p-2.5 text-left transition ${deductThisMonth === o.value ? 'border-brand-500 ring-1 ring-brand-500' : 'border-slate-200 hover:bg-slate-50'}`}>
                <span className="block text-sm font-semibold text-slate-900">{o.title}</span>
                <span className="mt-0.5 block text-xs text-slate-600">{o.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="r-start" label="Starts" type="date" value={form.start_date} onChange={set('start_date')} error={errors.start_date}
          hint={form.deduction_mode === 'auto' ? 'Past due dates (up to ~2 months) are recorded right away.' : undefined} />
        <Field id="r-end" label="Ends (optional)" type="date" value={form.end_date} onChange={set('end_date')} error={errors.end_date} />
      </div>
      <Select id="r-pay" label="Usually paid with" value={form.payment_method} onChange={set('payment_method')}>
        {PAYMENT_METHODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
      </Select>
      {isEdit && <p className="text-xs text-slate-500">Changes apply to upcoming dates. Expenses already recorded stay as they are.</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={saving}>{isEdit ? 'Save changes' : 'Add recurring expense'}</Button>
      </div>
    </form>
  )
}

/** Dashboard section: list and manage recurring expenses. `onChange` lets the dashboard refresh its numbers. */
export default function RecurringExpenses({ onChange }) {
  const { data: items, error, loading, reload, setData } = useAsync(() => routineService.list(), [])
  const [editing, setEditing] = useState(null) // null | {} (new) | item
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(null)
  const [flash, setFlash] = useState('')
  const [actionError, setActionError] = useState('')

  const changed = (msg) => { setFlash(msg); onChange?.() }

  const toggle = async (r) => {
    setBusy(r.id)
    setActionError('')
    try {
      const updated = r.active ? await routineService.pause(r.id) : await routineService.resume(r.id)
      setData((list) => list.map((x) => (x.id === r.id ? updated : x)))
      changed(r.active ? `"${r.name}" paused. Its upcoming dates no longer reserve money.` : `"${r.name}" resumed.`)
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    setBusy(toDelete.id)
    try {
      await routineService.remove(toDelete.id)
      setData((list) => list.filter((x) => x.id !== toDelete.id))
      changed(`"${toDelete.name}" deleted.`)
      setToDelete(null)
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card id="recurring" className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 font-medium text-slate-900"><Repeat className="h-4 w-4 text-brand-700" /> Recurring expenses</h2>
          <p className="text-xs text-slate-500">Rent, subscriptions and daily habits. Money is kept aside before each due date.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/planned"><Button variant="secondary" className="px-3 py-1.5"><CalendarClock className="h-4 w-4" /> Calendar</Button></Link>
          <Button className="px-3 py-1.5" onClick={() => setEditing({})}><Plus className="h-4 w-4" /> Add recurring expense</Button>
        </div>
      </div>
      <div className="space-y-2">
        <Alert type="success">{flash}</Alert>
        <Alert>{actionError}</Alert>
      </div>

      {loading ? <p className="py-4 text-sm text-slate-500">Loading…</p> : error ? (
        <div className="space-y-2"><Alert>{error}</Alert><Button variant="secondary" onClick={() => reload()}>Try again</Button></div>
      ) : items.length === 0 ? (
        <EmptyState icon={Repeat} title="No recurring expenses yet" action={<Button onClick={() => setEditing({})}><Plus className="h-4 w-4" /> Add your first one</Button>}>
          Add rent to have it deducted automatically each month, or a daily tea you record with one tap.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((r) => (
            <li key={r.id} className={`flex flex-wrap items-center gap-3 py-3 ${r.active ? '' : 'opacity-60'}`}>
              <CategoryIcon category={r.category} />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                  <span className="truncate">{r.name}</span>
                  <ModeBadge mode={r.deduction_mode} />
                  {!r.active && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">Paused</span>}
                </p>
                <p className="text-xs text-slate-500">{formatINR(r.amount_paise)} · {describeSchedule(r)} · from {fmtDate(r.start_date)}{r.end_date ? ` to ${fmtDate(r.end_date)}` : ''}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button onClick={() => setEditing(r)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label={`Edit ${r.name}`}><Pencil className="h-4 w-4" /></button>
                <button onClick={() => toggle(r)} disabled={busy === r.id} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 disabled:opacity-50" aria-label={r.active ? `Pause ${r.name}` : `Resume ${r.name}`}>
                  {r.active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </button>
                <button onClick={() => setToDelete(r)} className="rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600" aria-label={`Delete ${r.name}`}><Trash2 className="h-4 w-4" /></button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={editing !== null} title={editing?.id ? 'Edit recurring expense' : 'Add recurring expense'} onClose={() => setEditing(null)}>
        {editing !== null && (
          <RecurringForm
            key={editing.id || 'new'}
            initial={editing}
            onCancel={() => setEditing(null)}
            onSaved={(saved, isEdit) => {
              setData((list) => (isEdit ? list.map((x) => (x.id === saved.id ? saved : x)) : [...list, saved]))
              const thisMonth = saved.this_month_expense_id ? ` ${formatINR(saved.amount_paise)} recorded for this month.` : ''
              changed(isEdit ? `"${saved.name}" updated.`
                : saved.deduction_mode === 'auto' ? `"${saved.name}" added.${thisMonth} It will be deducted automatically on each due date.`
                  : `"${saved.name}" added.${thisMonth} Tap "Spent" when it happens.`)
              setEditing(null)
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete recurring expense?"
        message={toDelete && `"${toDelete.name}" and its upcoming dates will be removed. Expenses already recorded are kept.`}
        onConfirm={remove}
        onClose={() => setToDelete(null)}
        loading={busy === toDelete?.id}
      />
    </Card>
  )
}
