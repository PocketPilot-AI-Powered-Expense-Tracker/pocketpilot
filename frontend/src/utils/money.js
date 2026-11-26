// All amounts travel to/from the API as integer paise (₹1 = 100 paise).

const formatter = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })

export function formatINR(paise) {
  if (paise == null || Number.isNaN(paise)) return '—'
  const str = formatter.format(paise / 100)
  return str.endsWith('.00') ? str.slice(0, -3) : str
}

const RUPEE_PATTERN = /^\d{1,9}(\.\d{1,2})?$/

/** Parse a rupee string like "150" or "99.5" into integer paise, without float maths. Returns null if invalid. */
export function rupeesToPaise(value) {
  const s = String(value ?? '').trim().replace(/,/g, '')
  if (!RUPEE_PATTERN.test(s)) return null
  const [whole, frac = ''] = s.split('.')
  return Number(whole) * 100 + Number(frac.padEnd(2, '0'))
}

/** Integer paise -> editable rupee string ("8000", "99.50"). */
export function paiseToRupeesInput(paise) {
  if (paise == null) return ''
  const whole = Math.floor(paise / 100)
  const frac = paise % 100
  return frac ? `${whole}.${String(frac).padStart(2, '0')}` : String(whole)
}
