import { AlertTriangle, CheckCircle2, Eye, XCircle } from 'lucide-react'

const STATUS = {
  on_track: { label: 'On track', icon: CheckCircle2, cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    hint: 'Your spending pace fits your plan.' },
  watch: { label: 'Spending fast', icon: Eye, cls: 'bg-amber-50 text-amber-800 ring-amber-200',
    hint: 'You are spending faster than the month is passing.' },
  at_risk: { label: 'Savings at risk', icon: AlertTriangle, cls: 'bg-orange-50 text-orange-800 ring-orange-200',
    hint: 'Your planned expenses or savings target are no longer fully covered.' },
  over_budget: { label: 'Over budget', icon: XCircle, cls: 'bg-rose-50 text-rose-700 ring-rose-200',
    hint: 'You have spent more than your income this month.' },
}

export default function BudgetStatus({ status, showHint = false }) {
  const s = STATUS[status] || STATUS.on_track
  const Icon = s.icon
  return (
    <span className="inline-flex flex-col gap-1">
      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${s.cls}`}>
        <Icon className="h-3.5 w-3.5" /> {s.label}
      </span>
      {showHint && <span className="text-xs text-slate-500">{s.hint}</span>}
    </span>
  )
}
