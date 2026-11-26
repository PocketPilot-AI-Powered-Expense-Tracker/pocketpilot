import api from './api'

// AI calls can take a few seconds.
const slow = { timeout: 45000 }

export const aiService = {
  status: () => api.get('/api/ai/status').then((r) => r.data),
  ask: (question) => api.post('/api/ai/ask', { question }, slow).then((r) => r.data),
  propose: (text) => api.post('/api/ai/actions/propose', { text }, slow).then((r) => r.data),
  confirm: (id) => api.post(`/api/ai/actions/${id}/confirm`).then((r) => r.data),
  cancel: (id) => api.post(`/api/ai/actions/${id}/cancel`).then((r) => r.data),
  insights: () => api.get('/api/ai/insights', slow).then((r) => r.data),
  report: (offset = 0) => api.get('/api/ai/report', { params: { offset }, ...slow }).then((r) => r.data),
}
