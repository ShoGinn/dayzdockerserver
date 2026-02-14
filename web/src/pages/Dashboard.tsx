import {
  AlertCircle,
  Clock,
  MapIcon,
  Package,
  Play,
  RefreshCw,
  RotateCcw,
  Server,
  Square,
} from 'lucide-react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card, CardHeader } from '../components/Card'
import { StatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import { useMapInfo } from '../hooks/useMapInfo'
import { useOperation } from '../hooks/useOperation'
import { useServerStatus } from '../hooks/useServerStatus'
import styles from './Dashboard.module.css'

export function DashboardPage() {
  const { status, error, isLoading, refetch } = useServerStatus({ pollInterval: 3000 })
  const { mapInfo } = useMapInfo(status?.map || null)
  const { addToast } = useToast()

  const startOp = useOperation(api.startServer, {
    onSuccess: () => {
      addToast('success', 'Server starting...')
      setTimeout(refetch, 1000)
    },
    onError: err => addToast('error', err),
  })

  const stopOp = useOperation(api.stopServer, {
    onSuccess: () => {
      addToast('success', 'Server stopping...')
      setTimeout(refetch, 1000)
    },
    onError: err => addToast('error', err),
  })

  const restartOp = useOperation(api.restartServer, {
    onSuccess: () => {
      addToast('success', 'Server restarting...')
      setTimeout(refetch, 1000)
    },
    onError: err => addToast('error', err),
  })

  const isServerRunning = status?.state === 'running'
  const isServerStopped =
    status?.state === 'stopped' || status?.state === 'crashed' || status?.state === 'disabled'
  const isTransitioning = status?.state === 'starting' || status?.state === 'stopping'
  const anyOperationLoading = startOp.isLoading || stopOp.isLoading || restartOp.isLoading

  if (isLoading && !status) {
    return (
      <div className={styles.loading}>
        <RefreshCw className="animate-spin" size={32} />
        <span>Loading server status...</span>
      </div>
    )
  }

  if (error && !status) {
    return (
      <div className={styles.error}>
        <AlertCircle size={32} />
        <span>{error}</span>
        <Button onClick={refetch} variant="secondary">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Dashboard</h1>
          <p className={styles.subtitle}>Monitor and control your DayZ server</p>
        </div>
      </header>

      {/* Status Card */}
      <Card className={styles.statusCard}>
        <div className={styles.statusMain}>
          <div className={styles.statusLeft}>
            <StatusBadge state={status?.state || 'stopped'} size="lg" />
            {status?.message && <p className={styles.statusMessage}>{status.message}</p>}
          </div>

          <div className={styles.statusControls}>
            {isServerStopped && (
              <Button
                onClick={() => startOp.execute()}
                isLoading={startOp.isLoading}
                disabled={anyOperationLoading}
                icon={<Play size={18} />}
                size="lg"
              >
                Start Server
              </Button>
            )}

            {isServerRunning && (
              <>
                <Button
                  onClick={() => restartOp.execute()}
                  isLoading={restartOp.isLoading}
                  disabled={anyOperationLoading}
                  variant="secondary"
                  icon={<RotateCcw size={18} />}
                  size="lg"
                >
                  Restart
                </Button>
                <Button
                  onClick={() => stopOp.execute()}
                  isLoading={stopOp.isLoading}
                  disabled={anyOperationLoading}
                  variant="danger"
                  icon={<Square size={18} />}
                  size="lg"
                >
                  Stop
                </Button>
              </>
            )}

            {isTransitioning && (
              <Button disabled variant="secondary" size="lg">
                <RefreshCw className="animate-spin" size={18} />
                {status?.state === 'starting' ? 'Starting...' : 'Stopping...'}
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Stats Grid */}
      <div className={styles.statsGrid}>
        <Card className={styles.statCard}>
          <div className={styles.statIcon}>
            <Clock size={20} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Uptime</span>
            <span className={styles.statValue}>{status?.uptime_text || '—'}</span>
          </div>
        </Card>

        <Card className={styles.statCard}>
          <div className={styles.statIcon}>
            <MapIcon size={20} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Map</span>
            <div>
              <span className={styles.statValue}>{mapInfo?.name || '—'}</span>
              {mapInfo?.description && (
                <p className={styles.mapDescription}>{mapInfo.description}</p>
              )}
            </div>
          </div>
        </Card>

        <Card className={styles.statCard}>
          <div className={styles.statIcon}>
            <Server size={20} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Version</span>
            <span className={styles.statValue}>{status?.version || '—'}</span>
          </div>
        </Card>

        <Card className={styles.statCard}>
          <div className={styles.statIcon}>
            <Package size={20} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Active Mods</span>
            <span className={styles.statValue}>{status?.active_mods?.length ?? 0}</span>
          </div>
        </Card>
      </div>

      {/* Active Mods */}
      {status?.active_mods && status.active_mods.length > 0 && (
        <Card>
          <CardHeader title="Active Mods" subtitle={`${status.active_mods.length} mod(s) loaded`} />
          <div className={styles.modsList}>
            {status.active_mods.map(mod => (
              <a
                key={mod.id}
                href={mod.url}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.modItem}
              >
                <span className={styles.modName}>{mod.name || mod.id}</span>
                <span className={styles.modSize}>{mod.size}</span>
              </a>
            ))}
          </div>
        </Card>
      )}

      {/* Server Info */}
      {status?.restart_count !== undefined && status.restart_count > 0 && (
        <Card>
          <CardHeader title="Server Health" />
          <div className={styles.healthInfo}>
            <div className={styles.healthItem}>
              <span className={styles.healthLabel}>Restart Count</span>
              <span className={styles.healthValue}>{status.restart_count}</span>
            </div>
            {status.last_exit_code !== null && (
              <div className={styles.healthItem}>
                <span className={styles.healthLabel}>Last Exit Code</span>
                <span className={styles.healthValue}>{status.last_exit_code}</span>
              </div>
            )}
            <div className={styles.healthItem}>
              <span className={styles.healthLabel}>Auto-Restart</span>
              <span
                className={`${styles.healthValue} ${status.auto_restart ? styles.enabled : styles.disabled}`}
              >
                {status.auto_restart ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
