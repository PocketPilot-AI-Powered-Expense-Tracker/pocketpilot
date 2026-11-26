import { categoryMeta } from '../utils/constants'

export function CategoryIcon({ category, className = '' }) {
  const { icon: Icon } = categoryMeta(category)
  return (
    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 ${className}`}>
      <Icon className="h-4 w-4" />
    </span>
  )
}

export function CategoryBadge({ category }) {
  return <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{categoryMeta(category).label}</span>
}
