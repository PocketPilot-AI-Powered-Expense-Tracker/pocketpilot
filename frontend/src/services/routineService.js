import api from './api'

export const routineService = {
  list: () => api.get('/api/routines').then((r) => r.data),
  create: (data) => api.post('/api/routines', data).then((r) => r.data),
  update: (id, data) => api.put(`/api/routines/${id}`, data).then((r) => r.data),
  pause: (id) => api.post(`/api/routines/${id}/pause`).then((r) => r.data),
  resume: (id) => api.post(`/api/routines/${id}/resume`).then((r) => r.data),
  remove: (id) => api.delete(`/api/routines/${id}`),
}

export const occurrenceService = {
  list: (params) => api.get('/api/occurrences', { params }).then((r) => r.data),
  spend: (id, data = {}) => api.post(`/api/occurrences/${id}/spend`, data).then((r) => r.data),
  skip: (id) => api.post(`/api/occurrences/${id}/skip`).then((r) => r.data),
  restore: (id) => api.post(`/api/occurrences/${id}/restore`).then((r) => r.data),
  reschedule: (id, newDate) => api.post(`/api/occurrences/${id}/reschedule`, { new_date: newDate }).then((r) => r.data),
}
