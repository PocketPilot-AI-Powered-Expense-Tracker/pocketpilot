import { AlertTriangle, Info, Lightbulb, ThumbsUp } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import { aiService } from '../services/aiService'
import AiBadge, { FactBadge } from './AiBadge'
import { Card, EmptyState, Spinner } from './ui'

const ICON = { warning: AlertTriangle, info: Info, positive: ThumbsUp }
const TONE = { warning: 'text-amber-700 bg-amber-50', info: 'text-sky-700 bg-sky-50', positive: 'text-emerald-700 bg-emerald-50' }

export default function InsightsCard() {
  const { data, error, loading } = useAsync(() => aiService.insights(), [])
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-medium text-slate-900"><Lightbulb className="h-4 w-4 text-violet-600" /> Insights</h2>
        {data && !data.ai_available && <span className="text-xs text-slate-500">AI not configured: showing built-in tips</span>}
      </div>
      {loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-slate-500"><Spinner className="h-4 w-4" /> Looking at your spending…</div>
      ) : error ? (
        <p className="text-sm text-slate-500">Insights are unavailable right now.</p>
      ) : data.insights.length === 0 ? (
        <EmptyState icon={Lightbulb} title="Nothing to flag yet">Keep logging expenses. Patterns show up after a few days.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {data.insights.map((i) => {
            const Icon = ICON[i.severity]
            return (
              <li key={i.id} className="flex gap-3">
                <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${TONE[i.severity]}`}><Icon className="h-4 w-4" /></span>
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-medium text-slate-900">{i.title}</p>
                  <p className="text-sm text-slate-700"><FactBadge /> <span className="ml-1">{i.fact}</span></p>
                  <p className="text-sm text-slate-600"><AiBadge by={i.tip_by} /> <span className="ml-1">{i.tip}</span></p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
