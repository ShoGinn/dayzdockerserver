import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../api'
import { AuthProvider, useAuth } from './useAuth'

function AuthState() {
  const { isAuthenticated, isVerifying } = useAuth()
  if (isVerifying) return <span>verifying</span>
  return <span>{isAuthenticated ? 'authenticated' : 'anonymous'}</span>
}

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('AuthProvider token verification', () => {
  it('retains the token and session during a transient verification failure', async () => {
    localStorage.setItem('api_token', 'valid-token')
    vi.spyOn(api, 'verifyToken').mockRejectedValue(new TypeError('network unavailable'))

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>
    )

    expect(await screen.findByText('authenticated')).not.toBeNull()
    expect(localStorage.getItem('api_token')).toBe('valid-token')
  })

  it('clears the token when the API rejects it with 401', async () => {
    localStorage.setItem('api_token', 'invalid-token')
    vi.spyOn(api, 'verifyToken').mockRejectedValue(new ApiError(401, 'Invalid token'))

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>
    )

    expect(await screen.findByText('anonymous')).not.toBeNull()
    expect(localStorage.getItem('api_token')).toBeNull()
  })
})
