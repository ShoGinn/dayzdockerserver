import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { ApiError, api } from '../api'

interface AuthContextType {
  isAuthenticated: boolean
  isVerifying: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isVerifying, setIsVerifying] = useState(true)

  const login = (token: string) => {
    localStorage.setItem('api_token', token)
    setIsAuthenticated(true)
    setIsVerifying(false)
  }

  const logout = useCallback(() => {
    localStorage.removeItem('api_token')
    setIsAuthenticated(false)
    setIsVerifying(false)
  }, [])

  // Verify token on mount
  useEffect(() => {
    const token = localStorage.getItem('api_token')
    if (token) {
      api
        .verifyToken(token)
        .then(() => setIsAuthenticated(true))
        .catch(error => {
          if (error instanceof ApiError && error.status === 401) {
            logout()
            return
          }
          // The backend still enforces authentication. Preserve the local
          // session during transient network and server failures so a valid
          // token is not destroyed by an outage.
          setIsAuthenticated(true)
        })
        .finally(() => setIsVerifying(false))
    } else {
      setIsVerifying(false)
    }
  }, [logout])

  return (
    <AuthContext.Provider value={{ isAuthenticated, isVerifying, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
