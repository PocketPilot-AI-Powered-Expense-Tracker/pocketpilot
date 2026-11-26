import api from './api'

const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

export const pendingService = {
  list: (status = 'pending_review') => api.get('/api/pending-transactions', { params: { status } }).then((r) => r.data),
  summary: () => api.get('/api/pending-transactions/summary').then((r) => r.data),
  simulate: (data) => api.post('/api/pending-transactions/simulate', data).then((r) => r.data),
  /** Accept (optionally with edits). One idempotency key per user action, reused on retry. */
  accept: async (id, overrides = {}, key = newKey()) => {
    const send = () => api.post(`/api/pending-transactions/${id}/accept`, overrides, { headers: { 'Idempotency-Key': key } })
    try {
      return (await send()).data
    } catch (err) {
      // Network hiccup: retry once with the SAME key, so it can never create two expenses.
      if (!err.response) return (await send()).data
      throw err
    }
  },
  reject: (id) => api.post(`/api/pending-transactions/${id}/reject`).then((r) => r.data),
  restore: (id) => api.post(`/api/pending-transactions/${id}/restore`).then((r) => r.data),
}
