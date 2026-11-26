import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { setUnauthorizedHandler, tokenStore } from '../services/api'
import { authService } from '../services/authService'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.get()))

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    // Server rejected our token (expired or revoked): log out and tell the user why.
    setUnauthorizedHandler(() => {
      if (tokenStore.get()) {
        try { sessionStorage.setItem('pocketpilot_session_expired', '1') } catch { /* storage unavailable */ }
      }
      logout()
    })
    if (!tokenStore.get()) return
    authService
      .me()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false))
  }, [logout])

  const handleAuth = (data) => {
    tokenStore.set(data.access_token)
    setUser(data.user)
    return data.user
  }

  const value = useMemo(
    () => ({
      user,
      loading,
      login: async (creds) => handleAuth(await authService.login(creds)),
      register: async (payload) => handleAuth(await authService.register(payload)),
      logout,
      refreshUser: async () => setUser(await authService.me()),
      markBudgetCreated: () => setUser((u) => (u ? { ...u, has_budget: true } : u)),
      deleteAccount: async () => {
        await authService.deleteAccount()
        logout()
      },
    }),
    [user, loading, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
