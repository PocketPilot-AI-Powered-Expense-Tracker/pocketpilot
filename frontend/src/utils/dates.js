/** Local (browser) date as YYYY-MM-DD. */
export function todayISO() {
  const d = new Date()
  return toISO(d)
}

export function toISO(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export const parseISO = (iso) => new Date(`${iso}T00:00:00`)

export function addDays(iso, n) {
  const d = parseISO(iso)
  d.setDate(d.getDate() + n)
  return toISO(d)
}

export const fmtDate = (iso, opts = { day: 'numeric', month: 'short' }) => parseISO(iso).toLocaleDateString('en-IN', opts)

export function relativeDay(iso) {
  const today = todayISO()
  if (iso === today) return 'Today'
  if (iso === addDays(today, 1)) return 'Tomorrow'
  if (iso === addDays(today, -1)) return 'Yesterday'
  return fmtDate(iso, { weekday: 'short', day: 'numeric', month: 'short' })
}
