import { WEEKDAYS } from './constants'

export function describeSchedule(r) {
  if (r.frequency === 'daily') return 'Every day'
  if (r.frequency === 'weekly') return `Every ${WEEKDAYS[r.weekday]}`
  const n = r.day_of_month
  const suffix = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'
  return `Monthly on the ${n}${suffix}`
}
