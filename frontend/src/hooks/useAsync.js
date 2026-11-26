import { useCallback, useEffect, useState } from 'react'
import { getErrorMessage } from '../utils/errors'

/** Run an async loader on mount (and when deps change). Returns { data, error, loading, reload, setData }. */
export function useAsync(loader, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  const reload = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      setData(await run())
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [run])

  useEffect(() => { reload() }, [reload])

  return { data, error, loading, reload, setData }
}
