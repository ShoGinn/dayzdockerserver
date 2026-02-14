import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { ConfigPage } from './pages/Config'
import { DashboardPage } from './pages/Dashboard'
import { LoginPage } from './pages/Login'
import { LogsPage } from './pages/Logs'
import { MapsPage } from './pages/Maps'
import { ModsPage } from './pages/Mods'
import { SettingsPage } from './pages/Settings'
import './styles/globals.css'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  const { isAuthenticated } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/mods" element={<ModsPage />} />
        <Route path="/maps" element={<MapsPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
