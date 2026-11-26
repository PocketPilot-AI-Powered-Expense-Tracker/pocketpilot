import { CalendarClock, ChevronLeft, ChevronRight, Printer } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AiBadge from '../components/AiBadge'
import BudgetStatus from '../components/BudgetStatus'
import { CategoryBars } from '../components/charts'
import { Alert, Button, Card, EmptyState, FullPageLoader, PageHeader, StatCard } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { aiService } from '../services/aiService'
import { CHART, categoryMeta } from '../utils/constants'
import { fmtDate, relativeDay } from '../utils/dates'
import { formatINR } from '../utils/money'

function Row({ label, value, strong }) {
  return <div className="flex justify-between gap-4 py-1.5 text-sm"><dt className="text-slate-600">{label}</dt><dd className={strong ? 'font-semibold text-slate-900' : 'font-medium text-slate-800'}>{value}</dd></div>
}

function WeekdayChart({ data }) {
  const rows = data.map((d) => ({ ...d, short: d.day.slice(0, 3) }))
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <XAxis dataKey="short" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} />
        <YAxis hide />
        <Tooltip cursor={{ fill: '#f1f5f9' }} content={({ active, payload }) => active && payload?.length ? (
          <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">{payload[0].payload.day}: <b>{formatINR(payload[0].payload.amount_paise)}</b></div>
        ) : null} />
        <Bar dataKey="amount_paise" fill={CHART.series1} radius={[4, 4, 0, 0]} maxBarSize={32} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function Report() {
  const [offset, setOffset] = useState(0)
  const { data: r, error, loading, reload } = useAsync(() => aiService.report(offset), [offset])

  return (
    <div className="space-y-5">
      <PageHeader title="Monthly report" subtitle="All totals are calculated by PocketPilot. The written summary is AI-generated when AI is available."
        actions={<Button variant="secondary" onClick={() => window.print()} className="print:hidden"><Printer className="h-4 w-4" /> Print</Button>} />

      <div className="flex items-center justify-between print:hidden">
        <button onClick={() => setOffset((o) => Math.min(12, o + 1))} className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100"><ChevronLeft className="h-4 w-4" /> Earlier</button>
        <span className="text-sm font-medium text-slate-800">{r ? `${fmtDate(r.period.start)} – ${fmtDate(r.period.end, { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}{offset === 0 ? ' · this month so far' : ''}</span>
        <button onClick={() => setOffset((o) => Math.max(0, o - 1))} disabled={offset === 0} className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-30">Later <ChevronRight className="h-4 w-4" /></button>
      </div>

      {loading ? <FullPageLoader label="Preparing your report…" /> : error ? (
        <div className="space-y-3"><Alert>{error}</Alert><Button variant="secondary" onClick={() => reload()}>Try again</Button></div>
      ) : (
        <>
          <Card className="bg-gradient-to-br from-white to-brand-50/50">
            <div className="flex flex-wrap items-center gap-2"><AiBadge by={r.text.written_by} /><BudgetStatus status={r.totals.status} /></div>
            <h2 className="mt-2 text-xl font-semibold text-slate-900">{r.text.headline}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{r.text.summary}</p>
            {r.text.notice && <p className="mt-2 text-xs text-slate-500">{r.text.notice}</p>}
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard label="Total income" value={formatINR(r.totals.total_income_paise)} sub={r.totals.extra_income_paise ? `incl. ${formatINR(r.totals.extra_income_paise)} extra` : 'From your budget'} />
            <StatCard label="Spent" value={formatINR(r.totals.expenses_paise)} sub="Confirmed expenses" />
            <StatCard label="Remaining" value={formatINR(r.totals.remaining_paise)} sub="Income minus spending" />
            <StatCard label="Savings target" value={formatINR(r.totals.savings_target_paise)} sub={`${r.totals.savings_progress_pct}% protected`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 font-medium text-slate-900">Spending by category</h3>
              {r.categories.length ? <CategoryBars data={r.categories} /> : <EmptyState title="No expenses in this period" />}
              {r.top_category && <p className="mt-2 text-sm text-slate-600">Highest: <b>{categoryMeta(r.top_category.category).label}</b>, {formatINR(r.top_category.amount_paise)} ({r.top_category.pct}%)</p>}
            </Card>
            <Card>
              <h3 className="mb-1 font-medium text-slate-900">Compared with {r.comparison.basis}</h3>
              <dl className="divide-y divide-slate-100">
                <Row label="This period" value={formatINR(r.totals.expenses_paise)} />
                <Row label={r.comparison.basis[0].toUpperCase() + r.comparison.basis.slice(1)} value={formatINR(r.comparison.previous_total_paise)} />
                <Row label="Change" strong value={`${r.comparison.change_paise > 0 ? '+' : ''}${formatINR(r.comparison.change_paise)}${r.comparison.change_pct != null ? ` (${r.comparison.change_pct > 0 ? '+' : ''}${r.comparison.change_pct}%)` : ''}`} />
              </dl>
              {r.comparison.categories.length > 0 && (
                <table className="mt-3 w-full text-sm">
                  <thead><tr className="text-left text-xs text-slate-500"><th className="py-1 font-medium">Category</th><th className="py-1 text-right font-medium">Now</th><th className="py-1 text-right font-medium">Before</th><th className="py-1 text-right font-medium">Change</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {r.comparison.categories.map((c) => (
                      <tr key={c.category}>
                        <td className="py-1.5 text-slate-700">{categoryMeta(c.category).label}</td>
                        <td className="py-1.5 text-right">{formatINR(c.current_paise)}</td>
                        <td className="py-1.5 text-right text-slate-500">{formatINR(c.previous_paise)}</td>
                        <td className={`py-1.5 text-right font-medium ${c.change_paise > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>{c.change_paise > 0 ? '+' : ''}{formatINR(c.change_paise)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <h3 className="mb-1 font-medium text-slate-900">Planned vs actual</h3>
              <dl className="divide-y divide-slate-100">
                <Row label="Planned (recurring)" value={formatINR(r.planned_vs_actual.planned_paise)} />
                <Row label="Spent from plans" value={formatINR(r.planned_vs_actual.spent_from_plans_paise)} />
                <Row label="Skipped plans" value={formatINR(r.planned_vs_actual.skipped_paise)} />
                <Row label="Unplanned spending" strong value={formatINR(r.planned_vs_actual.unplanned_paise)} />
              </dl>
            </Card>
            <Card>
              <h3 className="mb-1 font-medium text-slate-900">Spending patterns</h3>
              {r.patterns.busiest_weekday ? <WeekdayChart data={r.patterns.weekday_totals} /> : <EmptyState title="No pattern yet" />}
              <dl className="divide-y divide-slate-100">
                {r.patterns.busiest_weekday && <Row label="Busiest day" value={r.patterns.busiest_weekday} />}
                <Row label="Average per day" value={formatINR(r.patterns.avg_per_day_paise)} />
                <Row label="Days with spending" value={`${r.patterns.days_with_spending} of ${r.patterns.days_counted}`} />
                <Row label="Small buys under ₹100" value={`${r.patterns.small_expenses_count} · ${formatINR(r.patterns.small_expenses_paise)}`} />
              </dl>
            </Card>
            <Card>
              <h3 className="mb-1 flex items-center gap-2 font-medium text-slate-900"><CalendarClock className="h-4 w-4" /> Upcoming commitments</h3>
              {r.period.is_current ? (
                r.upcoming.items.length ? (
                  <>
                    <ul className="divide-y divide-slate-100">
                      {r.upcoming.items.map((o, i) => <li key={i} className="flex justify-between py-1.5 text-sm"><span className="text-slate-700">{o.name} <span className="text-xs text-slate-500">· {relativeDay(o.date)}</span></span><span className="font-medium">{formatINR(o.amount_paise)}</span></li>)}
                    </ul>
                    <p className="mt-2 text-sm text-slate-600">Total reserved: <b>{formatINR(r.upcoming.reserved_paise)}</b></p>
                  </>
                ) : <p className="text-sm text-slate-500">Nothing planned for the rest of this month.</p>
              ) : <p className="text-sm text-slate-500">This month has ended.</p>}
            </Card>
          </div>

          <Card>
            <div className="mb-2 flex items-center gap-2"><h3 className="font-medium text-slate-900">Savings recommendations</h3><AiBadge by={r.text.written_by} /></div>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{r.text.recommendations.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </Card>
        </>
      )}
    </div>
  )
}
