import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../api'

interface AuthContextType {
  isAuthenticated: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return !!localStorage.getItem('api_token')
  })

  const login = (token: string) => {
    localStorage.setItem('api_token', token)
    setIsAuthenticated(true)
  }

  const logout = useCallback(() => {
    localStorage.removeItem('api_token')
    setIsAuthenticated(false)
  }, [])

  // Verify token on mount
  useEffect(() => {
    const token = localStorage.getItem('api_token')
    if (token) {
      // Quick health check to verify token is valid (mock-aware)
      api.verifyToken(token).catch(err => {
        if (
          err instanceof Error &&
          'status' in err &&
          (err as { status?: number }).status === 401
        ) {
          logout()
        }
      })
    }
  }, [logout])

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
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
