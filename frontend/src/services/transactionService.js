import api from './api'

const clean = (params) => Object.fromEntries(Object.entries(params || {}).filter(([, v]) => v !== '' && v != null))

export const expenseService = {
  list: (params) => api.get('/api/expenses', { params: clean(params) }).then((r) => r.data),
  get: (id) => api.get(`/api/expenses/${id}`).then((r) => r.data),
  create: (data) => api.post('/api/expenses', data).then((r) => r.data),
  update: (id, data) => api.put(`/api/expenses/${id}`, data).then((r) => r.data),
  remove: (id) => api.delete(`/api/expenses/${id}`),
}

export const incomeService = {
  list: (params) => api.get('/api/income', { params: clean(params) }).then((r) => r.data),
  get: (id) => api.get(`/api/income/${id}`).then((r) => r.data),
  create: (data) => api.post('/api/income', data).then((r) => r.data),
  update: (id, data) => api.put(`/api/income/${id}`, data).then((r) => r.data),
  remove: (id) => api.delete(`/api/income/${id}`),
}
