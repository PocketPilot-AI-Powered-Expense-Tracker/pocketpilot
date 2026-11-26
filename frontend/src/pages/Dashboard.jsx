import { AlertTriangle, ArrowDownLeft, BellRing, CalendarClock, Check, Info, PiggyBank, Plus, Receipt, ShieldCheck, TrendingDown, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import BudgetStatus from '../components/BudgetStatus'
import { CategoryIcon } from '../components/CategoryBadge'
import { CategoryBars, MonthlyTrendChart, PaceChart } from '../components/charts'
import InsightsCard from '../components/InsightsCard'
import RecurringExpenses, { ModeBadge } from '../components/RecurringExpenses'
import { Alert, Button, Card, EmptyState, FullPageLoader, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useAsync } from '../hooks/useAsync'
import { analyticsService } from '../services/analyticsService'
import { occurrenceService } from '../services/routineService'
import { fmtDate, relativeDay, todayISO } from '../utils/dates'
import { getErrorMessage } from '../utils/errors'
import { formatINR } from '../utils/money'

function Section({ title, action, children }) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-medium text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </Card>
  )
}

function HowCalculated({ s }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1 text-xs font-medium text-brand-100 hover:text-white">
        <Info className="h-3.5 w-3.5" /> {open ? 'Hide' : 'How is this calculated?'}
      </button>
      {open && (
        <dl className="mt-2 space-y-1 rounded-lg bg-white/10 p-3 text-xs text-brand-50">
          {[
            ['Total income this month', s.total_income_paise],
            ['− Spent so far', s.actual_expenses_paise],
            ['− Savings target', s.savings_target_paise],
            ['− Reserved for planned expenses', s.reserved_upcoming_paise],
            ['= Free to spend this month', s.free_to_spend_paise],
          ].map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt>{k}</dt><dd className="font-medium">{formatINR(v)}</dd></div>)}
          <p className="pt-1 text-brand-100">
            Spread over {s.days_remaining} {s.days_remaining === 1 ? 'day' : 'days'} that's {formatINR(s.daily_recommendation_paise)}/day
            (worked out at the start of today), minus {formatINR(s.spent_today_unplanned_paise)} of unplanned spending today.
          </p>
        </dl>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync(() => analyticsService.dashboard(), [])
  const { hash } = useLocation()
  const [spending, setSpending] = useState(null)
  const [doneIds, setDoneIds] = useState([]) // hide items right after "Spent", before the reload finishes
  const [spendMsg, setSpendMsg] = useState({ type: 'success', text: '' })
  const today = todayISO()

  // /dashboard#recurring (e.g. from the Planned page) scrolls to the recurring section.
  useEffect(() => {
    if (data && hash === '#recurring') document.getElementById('recurring')?.scrollIntoView({ behavior: 'smooth' })
  }, [data, hash])

  const refresh = () => reload({ silent: true })

  const markSpent = async (o) => {
    setSpending(o.id)
    setSpendMsg({ type: 'success', text: '' })
    try {
      await occurrenceService.spend(o.id)
      setDoneIds((ids) => [...ids, o.id])
      setSpendMsg({ type: 'success', text: `${o.name} (${formatINR(o.amount_paise)}) recorded as spent.` })
      refresh()
    } catch (err) {
      setSpendMsg({ type: 'error', text: getErrorMessage(err) })
    } finally {
      setSpending(null)
    }
  }

  if (loading) return <FullPageLoader label="Crunching your numbers…" />
  if (error) return <div className="space-y-3"><Alert>{error}</Alert><Button variant="secondary" onClick={() => reload()}>Try again</Button></div>

  const s = data.summary
  const spentPct = Math.min(100, s.spent_pct)
  const hasExpenses = data.categories.length > 0

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Hi, {user?.name?.split(' ')[0]} 👋</h1>
          <p className="mt-1 text-sm text-slate-500">
            {fmtDate(s.period_start)} – {fmtDate(s.period_end)} · {s.days_remaining} {s.days_remaining === 1 ? 'day' : 'days'} left
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/income/new"><Button variant="secondary"><ArrowDownLeft className="h-4 w-4" /> Income</Button></Link>
          <Link to="/expenses/new"><Button><Plus className="h-4 w-4" /> Expense</Button></Link>
        </div>
      </div>

      {s.actual_expenses_paise === 0 && s.period_start < todayISO() && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
          <p className="flex items-start gap-2 text-amber-900">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            Your month started on {fmtDate(s.period_start)}, but nothing is recorded yet. Already spent some money? Add it so your daily limit is accurate.
          </p>
          <Link to="/budget" className="font-medium text-amber-900 underline underline-offset-2">Add what I've spent</Link>
        </div>
      )}

      {/* Hero: safe to spend today */}
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <div className="rounded-2xl bg-gradient-to-br from-brand-700 to-brand-600 p-6 text-white shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm text-brand-100">Safe to spend today</p>
            <span className="rounded-full bg-white/95 px-0.5 py-0.5"><BudgetStatus status={s.status} /></span>
          </div>
          <p className="mt-2 text-4xl font-semibold tracking-tight">{formatINR(s.safe_to_spend_today_paise)}</p>
          <p className="mt-1 text-sm text-brand-100">
            Daily budget {formatINR(s.daily_recommendation_paise)} · {formatINR(Math.max(0, s.free_to_spend_paise))} free for the rest of the month
          </p>
          <HowCalculated s={s} />
        </div>

        <Card>
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-700">Budget used</span>
            <BudgetStatus status={s.status} showHint />
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-xs text-slate-500"><span>Spent {s.spent_pct}%</span><span>Month {s.elapsed_pct}% gone</span></div>
            <div className="relative mt-1.5 h-3 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={spentPct} aria-valuemin={0} aria-valuemax={100} aria-label="Share of spendable money used">
              <div className={`h-full rounded-full ${s.status === 'on_track' ? 'bg-brand-500' : s.status === 'watch' ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${spentPct}%` }} />
              <div className="absolute inset-y-0 w-0.5 bg-slate-700" style={{ left: `${s.elapsed_pct}%` }} title="Today" />
            </div>
          </div>
          <div className="mt-5">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Savings target {formatINR(s.savings_target_paise)}</span><span>{s.savings_progress_pct}% protected</span>
            </div>
            <div className="mt-1.5 h-3 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={s.savings_progress_pct} aria-valuemin={0} aria-valuemax={100} aria-label="Savings target protected">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${s.savings_progress_pct}%` }} />
            </div>
            <p className="mt-1.5 text-xs text-slate-500">If you only spend what's planned, you'll end the month with {formatINR(s.projected_end_balance_paise)}.</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="Total income" value={formatINR(s.total_income_paise)} icon={Wallet} tone="sky"
          sub={s.extra_income_paise ? `incl. ${formatINR(s.extra_income_paise)} extra` : 'Monthly budget'} />
        <StatCard label="Spent so far" value={formatINR(s.actual_expenses_paise)} icon={TrendingDown} tone="amber"
          sub={s.planned_spent_paise ? `${formatINR(s.planned_spent_paise)} from recurring` : 'Confirmed expenses only'} />
        <StatCard label="Remaining" value={formatINR(s.remaining_budget_paise)} icon={ShieldCheck} tone="brand" sub="Income minus spending" />
        <StatCard label="Reserved for plans" value={formatINR(s.reserved_upcoming_paise)} icon={CalendarClock} tone="slate"
          sub={`${s.upcoming_count} upcoming planned ${s.upcoming_count === 1 ? 'expense' : 'expenses'}`} />
      </div>

      {data.pending_review.count > 0 && (
        <Link to="/review" className="flex items-center gap-2 rounded-xl border-2 border-dashed border-amber-300 bg-amber-50/60 px-4 py-3 text-sm text-amber-900 hover:bg-amber-50">
          <BellRing className="h-4 w-4 shrink-0" />
          <span className="flex-1">
            {data.pending_review.count} detected {data.pending_review.count === 1 ? 'payment' : 'payments'} ({formatINR(data.pending_review.total_paise)}) waiting for review.
            <span className="text-amber-800/80"> Not included in the numbers above until you add {data.pending_review.count === 1 ? 'it' : 'them'}.</span>
          </span>
          <span className="font-semibold">Review</span>
        </Link>
      )}

      {s.overdue_count > 0 && (
        <Link to="/planned" className="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900 ring-1 ring-amber-200 hover:bg-amber-100">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {s.overdue_count} past recurring {s.overdue_count === 1 ? 'expense needs' : 'expenses need'} an answer: did you spend it or skip it?
        </Link>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <RecurringExpenses onChange={refresh} />

        <Section title="Coming up (next 7 days)" action={<Link to="/planned" className="text-sm font-medium text-brand-700 hover:underline">Calendar</Link>}>
          {spendMsg.text && <div className="mb-2"><Alert type={spendMsg.type}>{spendMsg.text}</Alert></div>}
          {data.upcoming.length === 0 ? (
            <EmptyState icon={CalendarClock} title="Nothing coming up">
              Add a recurring expense, like rent or daily tea, and PocketPilot keeps money aside for it.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.upcoming.filter((o) => !doneIds.includes(o.id)).map((o) => {
                const tapNow = o.deduction_mode !== 'auto' && o.scheduled_date <= today
                return (
                  <li key={o.id} className="flex items-center gap-3 py-2.5">
                    <CategoryIcon category={o.category} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800">{o.name}</p>
                      <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                        {relativeDay(o.scheduled_date)} <ModeBadge mode={o.deduction_mode} />
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-slate-700">{formatINR(o.amount_paise)}</span>
                    {tapNow && (
                      <Button className="px-2.5 py-1.5 text-xs" loading={spending === o.id} disabled={Boolean(spending)}
                        onClick={() => markSpent(o)} aria-label={`Mark ${o.name} as spent`}>
                        <Check className="h-3.5 w-3.5" /> Spent
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </Section>
      </div>

      <InsightsCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Where your money went">
          {hasExpenses ? <CategoryBars data={data.categories} /> : (
            <EmptyState icon={PiggyBank} title="No spending yet this month">Add an expense to see your category breakdown.</EmptyState>
          )}
        </Section>
        <Section title="Spending pace this month">
          {hasExpenses ? <PaceChart data={data.daily_trend} /> : (
            <EmptyState icon={TrendingDown} title="Nothing to chart yet">Your spending line will appear here.</EmptyState>
          )}
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Recent transactions" action={<Link to="/transactions" className="text-sm font-medium text-brand-700 hover:underline">See all</Link>}>
          {data.recent_transactions.length === 0 ? (
            <EmptyState icon={Receipt} title="No transactions yet" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_transactions.map((t) => (
                <li key={`${t.type}-${t.id}`} className="flex items-center gap-3 py-2.5">
                  {t.type === 'expense' ? <CategoryIcon category={t.category} /> : (
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><ArrowDownLeft className="h-4 w-4" /></span>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-800">{t.type === 'expense' ? t.description : t.source}</p>
                    <p className="text-xs text-slate-500">{relativeDay(t.date)}{t.auto_deducted ? ' · deducted automatically' : ''}</p>
                  </div>
                  <span className={`text-sm font-semibold ${t.type === 'income' ? 'text-emerald-700' : 'text-slate-900'}`}>
                    {t.type === 'income' ? '+' : '−'}{formatINR(t.amount_paise)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Income vs expenses (last 6 months)" action={<Link to="/report" className="text-sm font-medium text-brand-700 hover:underline">Monthly report</Link>}>
          <MonthlyTrendChart data={data.monthly_trend} />
          <p className="mt-2 text-xs text-slate-500">Past months use your current budget plan as the base income.</p>
        </Section>
      </div>
    </div>
  )
}
