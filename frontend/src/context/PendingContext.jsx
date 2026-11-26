import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { pendingService } from '../services/pendingService'

const PendingContext = createContext({ count: 0, refresh: () => {} })

/** Keeps the "awaiting review" badge count fresh (on navigation and on demand). */
export function PendingProvider({ children }) {
  const [count, setCount] = useState(0)
  const location = useLocation()
  const refresh = useCallback(() => {
    pendingService.summary().then((s) => setCount(s.pending_count)).catch(() => {})
  }, [])
  useEffect(() => { refresh() }, [location.pathname, refresh])
  return <PendingContext.Provider value={{ count, refresh }}>{children}</PendingContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const usePendingCount = () => useContext(PendingContext)
