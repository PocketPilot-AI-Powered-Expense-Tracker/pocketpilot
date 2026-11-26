import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Field, FullPageLoader } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { budgetService } from '../services/budgetService'
import { getErrorMessage } from '../utils/errors'
import { formatINR, paiseToRupeesInput, rupeesToPaise } from '../utils/money'
import { addDays, fmtDate, toISO, todayISO, parseISO } from '../utils/dates'

/** The budget month containing today, for a given start day (mirrors backend periods.py). */
function currentPeriod(startDay) {
  const today = todayISO()
  const t = parseISO(today)
  const start = new Date(t.getFullYear(), t.getMonth() - (t.getDate() >= startDay ? 0 : 1), startDay)
  const nextStart = new Date(start.getFullYear(), start.getMonth() + 1, startDay)
  const startISO = toISO(start)
  const endISO = addDays(toISO(nextStart), -1)
  const day = 86400000
  return {
    start: startISO,
    end: endISO,
    daysBefore: Math.round((t - start) / day),
    daysLeft: Math.round((parseISO(endISO) - t) / day) + 1,
    yesterday: addDays(today, -1),
  }
}

const EMPTY = { allowance: '', additional: '0', savings: '0', startDay: '1', spent: '' }

export default function BudgetSetup() {
  const { user, markBudgetCreated } = useAuth()
  const navigate = useNavigate()
  const isNew = !user?.has_budget
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (isNew) return
    budgetService
      .get()
      .then((b) =>
        setForm({
          allowance: paiseToRupeesInput(b.monthly_allowance_paise),
          additional: paiseToRupeesInput(b.additional_income_paise),
          savings: paiseToRupeesInput(b.savings_target_paise),
          startDay: String(b.period_start_day),
          spent: b.spent_before_today_paise ? paiseToRupeesInput(b.spent_before_today_paise) : '',
        }),
      )
      .catch((err) => setServerError(getErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [isNew])

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const allowance = rupeesToPaise(form.allowance)
  const additional = rupeesToPaise(form.additional || '0')
  const savings = rupeesToPaise(form.savings || '0')
  const startDay = Number(form.startDay)
  const startDayValid = Number.isInteger(startDay) && startDay >= 1 && startDay <= 28
  const period = startDayValid ? currentPeriod(startDay) : null
  const askSpent = Boolean(period && period.daysBefore > 0)
  const spent = rupeesToPaise(form.spent || '0')

  const validate = () => {
    const e = {}
    if (allowance === null) e.allowance = 'Enter an amount like 8000 or 8000.50.'
    if (additional === null) e.additional = 'Enter a valid amount (or 0).'
    if (savings === null) e.savings = 'Enter a valid amount (or 0).'
    if (!Number.isInteger(startDay) || startDay < 1 || startDay > 28) e.startDay = 'Pick a day between 1 and 28.'
    if (askSpent && spent === null) e.spent = 'Enter a valid amount (or leave it empty).'
    if (!e.allowance && !e.additional && !e.savings && savings > allowance + additional)
      e.savings = 'Savings target cannot be more than your monthly income.'
    return e
  }

  const onSubmit = async (ev) => {
    ev.preventDefault()
    setServerError('')
    setSuccess('')
    const v = validate()
    setErrors(v)
    if (Object.keys(v).length) return
    const payload = {
      monthly_allowance_paise: allowance,
      additional_income_paise: additional,
      savings_target_paise: savings,
      period_start_day: startDay,
      ...(askSpent ? { spent_before_today_paise: spent } : {}),
    }
    setSaving(true)
    try {
      if (isNew) {
        await budgetService.create(payload)
        markBudgetCreated()
        navigate('/dashboard', { replace: true })
      } else {
        await budgetService.update(payload)
        setSuccess('Budget updated.')
      }
    } catch (err) {
      setServerError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <FullPageLoader label="Loading your budget…" />

  const previewValid = allowance !== null && additional !== null && savings !== null
  const income = previewValid ? allowance + additional : null
  const spendable = previewValid ? income - savings : null
  const spentSoFar = askSpent && spent !== null ? spent : 0
  const leftForMonth = spendable === null ? null : spendable - spentSoFar
  const perDay = leftForMonth !== null && period ? Math.max(0, Math.floor(leftForMonth / period.daysLeft)) : null

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">{isNew ? `Welcome, ${user?.name?.split(' ')[0]}! Let's set your budget` : 'Your budget'}</h1>
      <p className="mt-1 text-sm text-slate-500">
        Tell PocketPilot what comes in each month and how much you want to save. You can change this anytime.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 grid gap-6 lg:grid-cols-[1fr_16rem]">
        <Card className="space-y-4">
          <Alert>{serverError}</Alert>
          <Alert type="success">{success}</Alert>
          <Field id="allowance" label="Monthly pocket money / allowance" prefix="₹" inputMode="decimal" placeholder="8000"
            value={form.allowance} onChange={set('allowance')} error={errors.allowance} />
          <Field id="additional" label="Additional monthly income" prefix="₹" inputMode="decimal" placeholder="0"
            value={form.additional} onChange={set('additional')} error={errors.additional}
            hint="Scholarship, part-time job, freelancing, etc." />
          <Field id="savings" label="Monthly savings target" prefix="₹" inputMode="decimal" placeholder="0"
            value={form.savings} onChange={set('savings')} error={errors.savings} />
          <Field id="startDay" label="Budget month starts on day" type="number" min={1} max={28}
            value={form.startDay} onChange={set('startDay')} error={errors.startDay}
            hint="Usually the day your allowance arrives (1–28)." />
          {askSpent && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
              <p className="text-sm font-medium text-amber-900">
                Your budget month started on {fmtDate(period.start)}, so {period.daysBefore} {period.daysBefore === 1 ? 'day has' : 'days have'} already passed.
              </p>
              <div className="mt-3">
                <Field id="spent" label={`How much have you already spent (${fmtDate(period.start)} – ${fmtDate(period.yesterday)})?`}
                  prefix="₹" inputMode="decimal" placeholder="0"
                  value={form.spent} onChange={set('spent')} error={errors.spent}
                  hint="A rough total is fine: food, travel, rent, shopping… It's saved as one expense dated yesterday, so today's limit stays fair. Leave empty if nothing." />
              </div>
            </div>
          )}
          <Button type="submit" loading={saving} className="w-full sm:w-auto">
            {isNew ? 'Save and continue' : 'Save changes'}
          </Button>
        </Card>

        <Card className="h-fit bg-brand-50/60 ring-brand-100">
          <p className="text-sm font-medium text-brand-800">Preview</p>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-600">Monthly income</dt><dd className="font-medium">{formatINR(income)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-600">Savings target</dt><dd className="font-medium">− {formatINR(previewValid ? savings : null)}</dd></div>
            <div className="flex justify-between border-t border-brand-100 pt-2"><dt className="text-slate-700">Available to spend</dt><dd className="font-semibold text-brand-700">{formatINR(spendable)}</dd></div>
            {askSpent && (
              <>
                <div className="flex justify-between"><dt className="text-slate-600">Already spent this month</dt><dd className="font-medium">− {formatINR(spent === null ? null : spentSoFar)}</dd></div>
                <div className="flex justify-between border-t border-brand-100 pt-2"><dt className="text-slate-700">Left for the rest of the month</dt>
                  <dd className={`font-semibold ${leftForMonth !== null && leftForMonth < 0 ? 'text-rose-600' : 'text-brand-700'}`}>{formatINR(leftForMonth)}</dd></div>
              </>
            )}
          </dl>
          {period && perDay !== null && (
            <div className="mt-4 rounded-lg bg-white/80 p-3 text-sm">
              <p className="text-slate-600">{period.daysLeft} {period.daysLeft === 1 ? 'day' : 'days'} left ({fmtDate(period.end)} end)</p>
              <p className="mt-0.5 text-lg font-semibold text-brand-800">≈ {formatINR(perDay)} / day</p>
              {leftForMonth < 0 && <p className="mt-1 text-xs text-rose-600">You've already spent more than this month's budget.</p>}
              <p className="mt-1 text-xs text-slate-500">Recurring expenses you plan are set aside from this on the dashboard.</p>
            </div>
          )}
        </Card>
      </form>
    </div>
  )
}
