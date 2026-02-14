import { type FormEvent, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { useAuth } from '../hooks/useAuth'
import styles from './Login.module.css'

export function LoginPage() {
  const { login } = useAuth()
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // Test the token via mock-aware API
      await api.verifyToken(token)
      login(token)
    } catch (err) {
      if (err instanceof Error && 'status' in err && (err as { status?: number }).status === 401) {
        setError('Invalid token')
      } else {
        setError('Failed to connect to server')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>DZ</span>
          <h1 className={styles.logoText}>Server Manager</h1>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="token" className={styles.label}>
              API Token
            </label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              className={styles.input}
              placeholder="Enter your API token"
              ref={inputRef}
            />
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <Button type="submit" isLoading={isLoading} className={styles.submit}>
            Login
          </Button>
        </form>

        <p className={styles.hint}>
          The API token is set in your <code>.env</code> file as <code>API_TOKEN</code>
        </p>
      </div>
    </div>
  )
}
