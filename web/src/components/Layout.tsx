import {
  FileText,
  LayoutDashboard,
  LogOut,
  Map as MapIcon,
  Menu,
  Package,
  Settings as SettingsIcon,
  Terminal,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import styles from './Layout.module.css'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/mods', icon: Package, label: 'Mods' },
  { to: '/maps', icon: MapIcon, label: 'Maps' },
  { to: '/config', icon: FileText, label: 'Config' },
  { to: '/logs', icon: Terminal, label: 'Logs' },
  { to: '/settings', icon: SettingsIcon, label: 'Settings' },
]

export function Layout() {
  const { logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeSidebar = () => setSidebarOpen(false)

  return (
    <div className={styles.layout}>
      <button
        type="button"
        className={styles.mobileMenuButton}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {sidebarOpen && (
        <button
          type="button"
          className={styles.overlay}
          onClick={closeSidebar}
          aria-label="Close menu"
        />
      )}

      <aside className={`${styles.sidebar} ${sidebarOpen ? styles.open : ''}`}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>DZ</span>
          <span className={styles.logoText}>Server Manager</span>
        </div>

        <nav className={styles.nav}>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={closeSidebar}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
            >
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <button type="button" className={styles.logoutButton} onClick={logout}>
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
