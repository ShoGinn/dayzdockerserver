import { useCallback, useState } from 'react'
import type { OperationResponse } from '../types'

interface UseOperationOptions {
  onSuccess?: (result: OperationResponse) => void
  onError?: (error: string) => void
}

export function useOperation<TArgs extends unknown[]>(
  operation: (...args: TArgs) => Promise<OperationResponse>,
  options: UseOperationOptions = {}
) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OperationResponse | null>(null)

  const execute = useCallback(
    async (...args: TArgs) => {
      setIsLoading(true)
      setError(null)
      setResult(null)

      try {
        const response = await operation(...args)
        setResult(response)
        options.onSuccess?.(response)
        return response
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Operation failed'
        setError(message)
        options.onError?.(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [operation, options]
  )

  const reset = useCallback(() => {
    setIsLoading(false)
    setError(null)
    setResult(null)
  }, [])

  return { execute, isLoading, error, result, reset }
}
