import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, Card, Field, FullPageLoader, PageHeader, TextArea } from '../components/ui'
import { incomeService } from '../services/transactionService'
import { INCOME_SOURCES } from '../utils/constants'
import { todayISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { paiseToRupeesInput, rupeesToPaise } from '../utils/money'

export default function IncomeForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const [form, setForm] = useState({ amount: '', source: 'Pocket money', date: todayISO(), description: '', counts_as_planned: true })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isEdit) return
    incomeService
      .get(id)
      .then((i) => setForm({ amount: paiseToRupeesInput(i.amount_paise), source: i.source, date: i.date,
        description: i.description || '', counts_as_planned: i.counts_as_planned }))
      .catch((err) => setServerError(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const pickSource = (s) => setForm({ ...form, source: s, counts_as_planned: s === 'Pocket money' || s === 'Allowance' })

  const onSubmit = async (ev) => {
    ev.preventDefault()
    setServerError('')
    const amount = rupeesToPaise(form.amount)
    const v = {}
    if (!amount) v.amount = 'Enter an amount greater than ₹0.'
    if (!form.source.trim()) v.source = 'Where did this money come from?'
    if (!form.date) v.date = 'Pick a date.'
    else if (form.date > todayISO()) v.date = 'Income cannot be dated in the future.'
    setErrors(v)
    if (Object.keys(v).length) return
    const payload = { amount_paise: amount, source: form.source.trim(), date: form.date,
      description: form.description.trim() || null, counts_as_planned: form.counts_as_planned }
    setSaving(true)
    try {
      if (isEdit) await incomeService.update(id, payload)
      else await incomeService.create(payload)
      navigate('/transactions?tab=income', { replace: true, state: { flash: isEdit ? 'Income updated.' : 'Income added.' } })
    } catch (err) {
      setServerError(getErrorMessage(err))
      setSaving(false)
    }
  }

  if (loading) return <FullPageLoader />

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title={isEdit ? 'Edit income' : 'Add income'} subtitle="Money you have received." />
      <Card>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <Alert>{serverError}</Alert>
          <Field id="amount" label="Amount" prefix="₹" inputMode="decimal" placeholder="2000" autoFocus={!isEdit}
            value={form.amount} onChange={set('amount')} error={errors.amount} />
          <div>
            <Field id="source" label="Source" list="income-sources" maxLength={60} value={form.source}
              onChange={set('source')} error={errors.source} />
            <datalist id="income-sources">{INCOME_SOURCES.map((s) => <option key={s} value={s} />)}</datalist>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {INCOME_SOURCES.map((s) => (
                <button type="button" key={s} onClick={() => pickSource(s)}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${form.source === s ? 'bg-brand-50 text-brand-800 ring-brand-300' : 'text-slate-600 ring-slate-200 hover:bg-slate-50'}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <Field id="date" label="Date received" type="date" max={todayISO()} value={form.date} onChange={set('date')} error={errors.date} />
          <TextArea id="description" label="Description (optional)" maxLength={200} value={form.description} onChange={set('description')} />

          <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand-600" checked={form.counts_as_planned}
              onChange={(e) => setForm({ ...form, counts_as_planned: e.target.checked })} />
            <span className="text-sm">
              <span className="font-medium text-slate-800">This is part of my regular monthly income</span>
              <span className="block text-slate-500">
                {form.counts_as_planned
                  ? 'Already included in your budget, so it will not be added again.'
                  : 'Extra money: it will be added on top of your monthly budget.'}
              </span>
            </span>
          </label>

          <div className="flex gap-2 pt-1">
            <Button type="submit" loading={saving}>{isEdit ? 'Save changes' : 'Add income'}</Button>
            <Link to="/transactions?tab=income"><Button type="button" variant="secondary">Cancel</Button></Link>
          </div>
        </form>
      </Card>
    </div>
  )
}
