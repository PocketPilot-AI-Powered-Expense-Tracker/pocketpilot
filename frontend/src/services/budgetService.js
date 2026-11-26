import api from './api'

export const budgetService = {
  get: () => api.get('/api/budget').then((r) => r.data),
  create: (data) => api.post('/api/budget', data).then((r) => r.data),
  update: (data) => api.put('/api/budget', data).then((r) => r.data),
}
