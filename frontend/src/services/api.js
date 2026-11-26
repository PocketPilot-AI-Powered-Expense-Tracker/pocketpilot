import axios from 'axios'

const TOKEN_KEY = 'pocketpilot_token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Listeners (e.g. AuthContext) are told when the server rejects our token.
let onUnauthorized = null
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const isAuthCall = error.config?.url?.startsWith('/api/auth/login') || error.config?.url?.startsWith('/api/auth/register')
    if (error.response?.status === 401 && !isAuthCall && onUnauthorized) onUnauthorized()
    return Promise.reject(error)
  },
)

export default api
