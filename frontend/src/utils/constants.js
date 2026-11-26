import { BookOpen, Bus, Clapperboard, HeartPulse, Home, MoreHorizontal, Repeat, ShoppingBag, Utensils } from 'lucide-react'

export const CATEGORIES = [
  { value: 'food', label: 'Food', icon: Utensils },
  { value: 'rent', label: 'Rent', icon: Home },
  { value: 'transportation', label: 'Transportation', icon: Bus },
  { value: 'shopping', label: 'Shopping', icon: ShoppingBag },
  { value: 'entertainment', label: 'Entertainment', icon: Clapperboard },
  { value: 'education', label: 'Education', icon: BookOpen },
  { value: 'subscriptions', label: 'Subscriptions', icon: Repeat },
  { value: 'personal_care', label: 'Personal care', icon: HeartPulse },
  { value: 'other', label: 'Other', icon: MoreHorizontal },
]
export const categoryMeta = (v) => CATEGORIES.find((c) => c.value === v) || CATEGORIES[CATEGORIES.length - 1]

export const PAYMENT_METHODS = [
  { value: 'upi', label: 'UPI' },
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card' },
  { value: 'net_banking', label: 'Net banking' },
  { value: 'wallet', label: 'Wallet' },
  { value: 'other', label: 'Other' },
]
export const paymentLabel = (v) => PAYMENT_METHODS.find((p) => p.value === v)?.label || v

export const INCOME_SOURCES = ['Pocket money', 'Allowance', 'Scholarship', 'Part-time job', 'Freelance', 'Gift', 'Other']

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

// Chart colours: validated categorical slots (blue, orange) + neutral ink.
export const CHART = {
  series1: '#2a78d6',
  series2: '#eb6834',
  grid: '#e2e8f0',
  axis: '#64748b',
}
