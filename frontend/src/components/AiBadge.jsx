import { Calculator, Sparkles } from 'lucide-react'

/** Makes it obvious whether text was written by AI or is a calculated fact. */
export default function AiBadge({ by }) {
  return by === 'ai' ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-violet-200">
      <Sparkles className="h-3 w-3" /> AI suggestion
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200">
      <Calculator className="h-3 w-3" /> PocketPilot tip
    </span>
  )
}

export function FactBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
      <Calculator className="h-3 w-3" /> Calculated fact
    </span>
  )
}
