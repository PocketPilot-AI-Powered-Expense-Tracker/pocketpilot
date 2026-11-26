import api from './api'

export const analyticsService = {
  dashboard: () => api.get('/api/analytics/dashboard').then((r) => r.data),
  safeToSpend: () => api.get('/api/analytics/safe-to-spend').then((r) => r.data),
  categories: (offset = 0) => api.get('/api/analytics/categories', { params: { offset } }).then((r) => r.data),
  monthlyComparison: (months = 6) => api.get('/api/analytics/monthly-comparison', { params: { months } }).then((r) => r.data),
}
