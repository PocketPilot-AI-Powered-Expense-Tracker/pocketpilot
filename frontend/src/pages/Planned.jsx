import { AlertTriangle, CalendarDays, Check, ChevronLeft, ChevronRight, Clock, RotateCcw, SkipForward } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CategoryIcon } from '../components/CategoryBadge'
import Modal from '../components/Modal'
import { Alert, Button, Card, EmptyState, Field, FullPageLoader, PageHeader, Select } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { budgetService } from '../services/budgetService'
import { occurrenceService } from '../services/routineService'
import { PAYMENT_METHODS } from '../utils/constants'
import { addDays, fmtDate, parseISO, relativeDay, toISO, todayISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { formatINR, paiseToRupeesInput, rupeesToPaise } from '../utils/money'

/** Budget period that is `offset` periods away from the current one (display only). */
function periodAt(currentStart, startDay, offset) {
  const d = parseISO(currentStart)
  const start = new Date(d.getFullYear(), d.getMonth() + offset, startDay)
  const end = new Date(start.getFullYear(), start.getMonth() + 1, startDay - 1)
  return { start: toISO(start), end: toISO(end) }
}

const STATUS_STYLE = {
  planned: 'bg-sky-50 text-sky-700 ring-sky-200',
  spent: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  skipped: 'bg-slate-100 text-slate-500 ring-slate-200',
}

function OccurrenceRow({ o, onAction, busy, today }) {
  const overdue = o.status === 'planned' && o.scheduled_date < today
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <CategoryIcon category={o.category} />
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm font-medium ${o.status === 'skipped' ? 'text-slate-400 line-through' : 'text-slate-800'}`}>{o.name}</p>
        <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span>{relativeDay(o.scheduled_date)}</span>
          {o.rescheduled && <span>moved from {fmtDate(o.original_date)}</span>}
          <span className={`rounded-full px-2 py-0.5 font-medium capitalize ring-1 ${overdue ? 'bg-amber-50 text-amber-800 ring-amber-200' : STATUS_STYLE[o.status]}`}>
            {overdue ? 'Did this happen?' : o.status}
          </span>
        </p>
      </div>
      <span className="text-sm font-semibold text-slate-900">{formatINR(o.amount_paise)}</span>
      <div className="flex w-full flex-wrap gap-1.5 sm:w-auto">
        {o.status === 'planned' && (
          <>
            <Button className="px-2.5 py-1.5 text-xs" onClick={() => onAction('spend', o)} disabled={busy}><Check className="h-3.5 w-3.5" /> Spent</Button>
            <Button variant="secondary" className="px-2.5 py-1.5 text-xs" onClick={() => onAction('skip', o)} disabled={busy}><SkipForward className="h-3.5 w-3.5" /> Skip</Button>
            <Button variant="secondary" className="px-2.5 py-1.5 text-xs" onClick={() => onAction('reschedule', o)} disabled={busy}><Clock className="h-3.5 w-3.5" /> Move</Button>
          </>
        )}
        {o.status === 'skipped' && (
          <Button variant="secondary" className="px-2.5 py-1.5 text-xs" onClick={() => onAction('restore', o)} disabled={busy}><RotateCcw className="h-3.5 w-3.5" /> Restore</Button>
        )}
        {o.status === 'spent' && o.expense_id && (
          <Link to={`/expenses/${o.expense_id}/edit`} className="text-xs font-medium text-brand-700 hover:underline">View expense</Link>
        )}
      </div>
    </li>
  )
}

export default function Planned() {
  const today = todayISO()
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(today)
  const [modal, setModal] = useState(null) // { type: 'spend'|'reschedule', o }
  const [modalForm, setModalForm] = useState({})
  const [modalError, setModalError] = useState('')
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState('')
  const [actionError, setActionError] = useState('')

  const budget = useAsync(() => budgetService.get(), [])
  const period = budget.data ? periodAt(budget.data.current_period.start, budget.data.period_start_day, offset) : null
  const occ = useAsync(() => (period ? occurrenceService.list({ from: period.start, to: period.end }) : Promise.resolve(null)),
    [period?.start, period?.end])

  const byDay = useMemo(() => {
    const m = {}
    for (const o of occ.data || []) (m[o.scheduled_date] ||= []).push(o)
    return m
  }, [occ.data])

  const weeks = useMemo(() => {
    if (!period) return []
    const start = parseISO(period.start)
    const lead = (start.getDay() + 6) % 7 // Monday-first
    const days = []
    for (let i = 0; i < lead; i++) days.push(null)
    for (let d = period.start; d <= period.end; d = addDays(d, 1)) days.push(d)
    while (days.length % 7) days.push(null)
    return Array.from({ length: days.length / 7 }, (_, i) => days.slice(i * 7, i * 7 + 7))
  }, [period?.start, period?.end]) // eslint-disable-line react-hooks/exhaustive-deps

  const runAction = async (type, o, body) => {
    setBusy(true)
    setActionError('')
    try {
      if (type === 'skip') await occurrenceService.skip(o.id)
      if (type === 'restore') await occurrenceService.restore(o.id)
      if (type === 'spend') await occurrenceService.spend(o.id, body)
      if (type === 'reschedule') await occurrenceService.reschedule(o.id, body)
      const msg = { skip: `Skipped "${o.name}". ${formatINR(o.amount_paise)} is free to use again.`,
        restore: `"${o.name}" is planned again.`, spend: `"${o.name}" added to your expenses.`,
        reschedule: `"${o.name}" moved to ${relativeDay(body)}.` }[type]
      setFlash(msg)
      setModal(null)
      await occ.reload({ silent: true })
    } catch (err) {
      if (modal) setModalError(getErrorMessage(err))
      else setActionError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const onAction = (type, o) => {
    setModalError('')
    if (type === 'spend') {
      setModalForm({ amount: paiseToRupeesInput(o.amount_paise), date: o.scheduled_date > today ? today : o.scheduled_date, payment_method: 'upi' })
      setModal({ type, o })
    } else if (type === 'reschedule') {
      setModalForm({ date: o.scheduled_date < today ? today : o.scheduled_date })
      setModal({ type, o })
    } else runAction(type, o)
  }

  const submitModal = (e) => {
    e.preventDefault()
    const { type, o } = modal
    if (type === 'spend') {
      const amount = rupeesToPaise(modalForm.amount)
      if (!amount) return setModalError('Enter the amount you actually spent.')
      if (!modalForm.date || modalForm.date > today) return setModalError('Pick today or an earlier date.')
      runAction('spend', o, { amount_paise: amount, date: modalForm.date, payment_method: modalForm.payment_method })
    } else {
      if (!modalForm.date || modalForm.date < today) return setModalError('Pick today or a future date.')
      runAction('reschedule', o, modalForm.date)
    }
  }

  if (budget.loading) return <FullPageLoader />
  if (budget.error) return <Alert>{budget.error}</Alert>

  const list = occ.data || []
  const overdue = offset === 0 ? list.filter((o) => o.status === 'planned' && o.scheduled_date < today) : []
  const reserved = list.filter((o) => o.status === 'planned' && o.scheduled_date >= today).reduce((s, o) => s + o.amount_paise, 0)
  const selectedList = byDay[selected] || []

  return (
    <div>
      <PageHeader title="Planned expenses" subtitle="Upcoming dates of your recurring expenses. Planned items hold money aside but are not counted as spent until recorded."
        actions={<Link to="/dashboard#recurring"><Button variant="secondary">Manage recurring expenses</Button></Link>} />
      <div className="mb-3 space-y-2"><Alert type="success">{flash}</Alert><Alert>{actionError}</Alert></div>

      {overdue.length > 0 && (
        <Card className="mb-4 ring-amber-200">
          <div className="flex items-center gap-2 text-amber-800"><AlertTriangle className="h-4 w-4" /><h2 className="font-medium">Needs your answer</h2></div>
          <p className="mt-1 text-sm text-slate-500">These planned dates have passed. Did you spend the money? They don't affect your budget until you mark them spent.</p>
          <ul className="mt-1 divide-y divide-slate-100">
            {overdue.map((o) => <OccurrenceRow key={o.id} o={o} onAction={onAction} busy={busy} today={today} />)}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <button onClick={() => setOffset((x) => x - 1)} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Previous period"><ChevronLeft className="h-5 w-5" /></button>
            <div className="text-center">
              <p className="font-medium text-slate-900">{period && `${fmtDate(period.start)} – ${fmtDate(period.end, { day: 'numeric', month: 'short', year: 'numeric' })}`}</p>
              {offset === 0 && <p className="text-xs text-slate-500">{formatINR(reserved)} reserved for the rest of this period</p>}
            </div>
            <button onClick={() => setOffset((x) => x + 1)} disabled={offset >= 2} className="rounded-lg p-2 hover:bg-slate-100 disabled:opacity-30" aria-label="Next period"><ChevronRight className="h-5 w-5" /></button>
          </div>
          {occ.loading ? <FullPageLoader /> : occ.error ? <Alert>{occ.error}</Alert> : (
            <div role="grid" aria-label="Planned expenses calendar" className="space-y-1">
              <div className="grid grid-cols-7 gap-1 pb-1 text-center text-xs font-medium text-slate-500">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => <span key={d}>{d}</span>)}
              </div>
              {weeks.map((w, i) => (
                <div key={i} className="grid grid-cols-7 gap-1">
                  {w.map((d, j) => {
                    if (!d) return <span key={j} />
                    const items = byDay[d] || []
                    const planned = items.filter((o) => o.status === 'planned')
                    const total = planned.reduce((s, o) => s + o.amount_paise, 0)
                    const allDone = items.length > 0 && planned.length === 0
                    return (
                      <button key={d} onClick={() => setSelected(d)} aria-pressed={selected === d}
                        className={`flex min-h-14 flex-col items-center rounded-lg p-1 text-xs transition sm:min-h-16 ${
                          selected === d ? 'bg-brand-600 text-white' : d === today ? 'bg-brand-50 ring-1 ring-brand-300' : 'bg-slate-50 hover:bg-slate-100'}`}>
                        <span className="font-medium">{parseISO(d).getDate()}</span>
                        {total > 0 && <span className={`mt-auto truncate text-[10px] sm:text-xs ${selected === d ? 'text-white' : d < today ? 'text-amber-700' : 'text-sky-700'}`}>{formatINR(total)}</span>}
                        {allDone && <Check className={`mt-auto h-3 w-3 ${selected === d ? 'text-white' : 'text-emerald-600'}`} />}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="h-fit">
          <h2 className="font-medium text-slate-900">{relativeDay(selected)}</h2>
          {selectedList.length === 0 ? (
            <EmptyState icon={CalendarDays} title="Nothing planned">
              {list.length === 0 && offset === 0 ? <>Add a <Link to="/dashboard#recurring" className="text-brand-700 underline">recurring expense</Link> to plan regular spending.</> : 'Pick another day on the calendar.'}
            </EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {selectedList.map((o) => <OccurrenceRow key={o.id} o={o} onAction={onAction} busy={busy} today={today} />)}
            </ul>
          )}
        </Card>
      </div>

      <Modal open={Boolean(modal)} title={modal?.type === 'spend' ? `Mark "${modal?.o.name}" as spent` : `Move "${modal?.o.name}"`} onClose={() => setModal(null)}>
        {modal && (
          <form onSubmit={submitModal} noValidate className="space-y-4">
            <Alert>{modalError}</Alert>
            {modal.type === 'spend' ? (
              <>
                <p className="text-sm text-slate-500">This creates one real expense. Change the amount if you spent a different sum.</p>
                <Field id="m-amount" label="Amount spent" prefix="₹" inputMode="decimal" value={modalForm.amount} onChange={(e) => setModalForm({ ...modalForm, amount: e.target.value })} />
                <Field id="m-date" label="Date" type="date" max={today} value={modalForm.date} onChange={(e) => setModalForm({ ...modalForm, date: e.target.value })} />
                <Select id="m-pay" label="Paid with" value={modalForm.payment_method} onChange={(e) => setModalForm({ ...modalForm, payment_method: e.target.value })}>
                  {PAYMENT_METHODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </>
            ) : (
              <Field id="m-new" label="New date" type="date" min={today} value={modalForm.date} onChange={(e) => setModalForm({ ...modalForm, date: e.target.value })} />
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setModal(null)}>Cancel</Button>
              <Button type="submit" loading={busy}>{modal.type === 'spend' ? 'Add to expenses' : 'Move'}</Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
