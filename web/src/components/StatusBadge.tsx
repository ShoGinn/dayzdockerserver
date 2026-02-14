import type { ServerState } from '../types'
import styles from './StatusBadge.module.css'

interface StatusBadgeProps {
  state: ServerState
  size?: 'sm' | 'md' | 'lg'
  showPulse?: boolean
}

const stateLabels: Record<ServerState, string> = {
  stopped: 'Stopped',
  starting: 'Starting...',
  running: 'Running',
  stopping: 'Stopping...',
  crashed: 'Crashed',
  disabled: 'Disabled',
  maintenance: 'Maintenance',
}

const stateColors: Record<ServerState, string> = {
  stopped: 'stopped',
  starting: 'warning',
  running: 'running',
  stopping: 'warning',
  crashed: 'danger',
  disabled: 'muted',
  maintenance: 'muted',
}

export function StatusBadge({ state, size = 'md', showPulse = true }: StatusBadgeProps) {
  const colorClass = stateColors[state]
  const shouldPulse =
    showPulse && (state === 'running' || state === 'starting' || state === 'stopping')

  return (
    <div className={`${styles.badge} ${styles[colorClass]} ${styles[size]}`}>
      <span className={`${styles.dot} ${shouldPulse ? styles.pulse : ''}`} />
      <span className={styles.label}>{stateLabels[state]}</span>
    </div>
  )
}
