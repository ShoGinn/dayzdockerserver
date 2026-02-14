import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { ServerStatus } from '../types'

interface UseServerStatusOptions {
  pollInterval?: number
  enabled?: boolean
}

export function useServerStatus(options: UseServerStatusOptions = {}) {
  const { pollInterval = 5000, enabled = true } = options

  const [status, setStatus] = useState<ServerStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getStatus()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch status')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return

    fetchStatus()

    const interval = setInterval(fetchStatus, pollInterval)
    return () => clearInterval(interval)
  }, [fetchStatus, pollInterval, enabled])

  return { status, error, isLoading, refetch: fetchStatus }
}
