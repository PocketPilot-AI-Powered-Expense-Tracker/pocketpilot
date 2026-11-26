import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, Card, Field, FullPageLoader, PageHeader, Select, TextArea } from '../components/ui'
import { expenseService } from '../services/transactionService'
import { CATEGORIES, PAYMENT_METHODS } from '../utils/constants'
import { todayISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { paiseToRupeesInput, rupeesToPaise } from '../utils/money'

const EMPTY = { amount: '', category: 'food', description: '', date: todayISO(), payment_method: 'upi', notes: '' }

export default function ExpenseForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const [form, setForm] = useState({ ...EMPTY, date: todayISO() })
  const [source, setSource] = useState('manual')
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isEdit) return
    expenseService
      .get(id)
      .then((e) => {
        setForm({ amount: paiseToRupeesInput(e.amount_paise), category: e.category, description: e.description,
          date: e.date, payment_method: e.payment_method, notes: e.notes || '' })
        setSource(e.source)
      })
      .catch((err) => setServerError(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const onSubmit = async (ev) => {
    ev.preventDefault()
    setServerError('')
    const amount = rupeesToPaise(form.amount)
    const v = {}
    if (!amount) v.amount = 'Enter an amount greater than ₹0, e.g. 150 or 99.50.'
    if (!form.description.trim()) v.description = 'Add a short description, e.g. "Lunch".'
    if (!form.date) v.date = 'Pick a date.'
    else if (form.date > todayISO()) v.date = 'Expenses cannot be in the future. Add a recurring expense to plan ahead.'
    setErrors(v)
    if (Object.keys(v).length) return
    const payload = { amount_paise: amount, category: form.category, description: form.description.trim(),
      date: form.date, payment_method: form.payment_method, notes: form.notes.trim() || null }
    setSaving(true)
    try {
      if (isEdit) await expenseService.update(id, payload)
      else await expenseService.create(payload)
      navigate('/transactions?tab=expenses', { replace: true, state: { flash: isEdit ? 'Expense updated.' : 'Expense added.' } })
    } catch (err) {
      setServerError(getErrorMessage(err))
      setSaving(false)
    }
  }

  if (loading) return <FullPageLoader />

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title={isEdit ? 'Edit expense' : 'Add expense'} subtitle="Money you have actually spent." />
      <Card>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Alert>{serverError}</Alert>
          {source === 'routine' && <Alert type="success">This expense came from a recurring expense. Deleting it puts the date back on your calendar (or marks it skipped if it was deducted automatically).</Alert>}
          {source === 'upi_review' && <Alert type="success">This expense was added from a detected UPI payment you reviewed.</Alert>}
          <Field id="amount" label="Amount" prefix="₹" inputMode="decimal" placeholder="150" autoFocus={!isEdit}
            value={form.amount} onChange={set('amount')} error={errors.amount} />
          <div>
            <span className="mb-1.5 block text-sm font-medium text-slate-700">Category</span>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="Category">
              {CATEGORIES.map(({ value, label, icon: Icon }) => (
                <button type="button" key={value} role="radio" aria-checked={form.category === value}
                  onClick={() => setForm({ ...form, category: value })}
                  className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs font-medium transition ${
                    form.category === value ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                  <Icon className="h-4 w-4 shrink-0" /> {label}
                </button>
              ))}
            </div>
          </div>
          <Field id="description" label="Description" placeholder="Lunch at canteen" maxLength={120}
            value={form.description} onChange={set('description')} error={errors.description} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="date" label="Date" type="date" max={todayISO()} value={form.date} onChange={set('date')} error={errors.date} />
            <Select id="payment_method" label="Paid with" value={form.payment_method} onChange={set('payment_method')}>
              {PAYMENT_METHODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </Select>
          </div>
          <TextArea id="notes" label="Notes (optional)" maxLength={500} value={form.notes} onChange={set('notes')} />
          <div className="flex gap-2 pt-1">
            <Button type="submit" loading={saving}>{isEdit ? 'Save changes' : 'Add expense'}</Button>
            <Link to="/transactions"><Button type="button" variant="secondary">Cancel</Button></Link>
          </div>
        </form>
      </Card>
    </div>
  )
}
