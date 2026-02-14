import {
  AlertTriangle,
  Download,
  FileX,
  HardDrive,
  RefreshCw,
  Shield,
  ToggleLeft,
  ToggleRight,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card, CardHeader } from '../components/Card'
import { useToast } from '../components/Toast'
import { useOperation } from '../hooks/useOperation'
import { useServerStatus } from '../hooks/useServerStatus'
import type { SteamLoginStatus } from '../types'
import styles from './Settings.module.css'

type StorageDir = {
  name: string
  path: string
  size_bytes: number
  size_human: string
  file_count: number
}

type CleanupInfo = {
  items: {
    core_dumps: Array<{ name: string; size_human: string }>
    crash_dumps: Array<{ name: string; size_human: string }>
    log_files: Array<{ name: string; size_human: string }>
    temp_files: Array<{ name: string; size_human: string }>
  }
  total_size_human: string
  counts: Record<string, number>
}

export function SettingsPage() {
  const { status, refetch } = useServerStatus()
  const [steamStatus, setSteamStatus] = useState<SteamLoginStatus | null>(null)
  const [storageDirs, setStorageDirs] = useState<StorageDir[]>([])
  const [storageMap, setStorageMap] = useState<string>('')
  const [storageTotalSize, setStorageTotalSize] = useState<string>('0 B')
  const [cleanupInfo, setCleanupInfo] = useState<CleanupInfo | null>(null)
  const { addToast } = useToast()

  const fetchStorageInfo = useCallback(async () => {
    try {
      const res = await api.getStorageInfo()
      setStorageDirs(res.storage_dirs)
      setStorageMap(res.map)
      setStorageTotalSize(res.total_size_human)
    } catch {
      // Ignore errors
    }
  }, [])

  const fetchCleanupInfo = useCallback(async () => {
    try {
      const res = await api.getCleanupInfo()
      setCleanupInfo(res)
    } catch {
      // Ignore errors
    }
  }, [])

  useEffect(() => {
    api
      .getSteamStatus()
      .then(setSteamStatus)
      .catch(() => {})
    fetchStorageInfo()
    fetchCleanupInfo()
  }, [fetchStorageInfo, fetchCleanupInfo])

  const installOp = useOperation(api.installServer, {
    onSuccess: () => addToast('success', 'Server installed successfully'),
    onError: err => addToast('error', err),
  })

  const updateOp = useOperation(api.updateServer, {
    onSuccess: () => addToast('success', 'Server updated successfully'),
    onError: err => addToast('error', err),
  })

  const enableAutoRestartOp = useOperation(api.enableAutoRestart, {
    onSuccess: () => {
      addToast('success', 'Auto-restart enabled')
      refetch()
    },
    onError: err => addToast('error', err),
  })

  const disableAutoRestartOp = useOperation(api.disableAutoRestart, {
    onSuccess: () => {
      addToast('success', 'Auto-restart disabled')
      refetch()
    },
    onError: err => addToast('error', err),
  })

  const enableMaintenanceOp = useOperation(api.enableMaintenance, {
    onSuccess: () => {
      addToast('success', 'Maintenance mode enabled')
      refetch()
    },
    onError: err => addToast('error', err),
  })

  const disableMaintenanceOp = useOperation(api.disableMaintenance, {
    onSuccess: () => {
      addToast('success', 'Maintenance mode disabled')
      refetch()
    },
    onError: err => addToast('error', err),
  })

  const testSteamOp = useOperation(api.testSteamLogin, {
    onSuccess: res => addToast(res.success ? 'success' : 'warning', res.message),
    onError: err => addToast('error', err),
  })

  const wipeStorageOp = useOperation(api.wipeStorage, {
    onSuccess: res => {
      addToast('success', res.message)
      fetchStorageInfo()
    },
    onError: err => addToast('error', err),
  })

  const cleanupOp = useOperation(api.cleanupServerFiles, {
    onSuccess: res => {
      addToast('success', res.message)
      fetchCleanupInfo()
    },
    onError: err => addToast('error', err),
  })

  const handleWipeStorage = (storageName?: string) => {
    const msg = storageName
      ? `This will DELETE all persistence data in ${storageName}. Player inventories, bases, and vehicles will be lost. Continue?`
      : `This will DELETE ALL persistence data. Player inventories, bases, and vehicles will be lost. Continue?`

    if (confirm(msg)) {
      wipeStorageOp.execute(storageName)
    }
  }

  const handleCleanup = () => {
    if (confirm('Delete all core dumps, crash dumps, and temp files from /serverfiles?')) {
      cleanupOp.execute({
        core_dumps: true,
        crash_dumps: true,
        temp_files: true,
        log_files: false,
      })
    }
  }

  const totalCleanupItems = cleanupInfo
    ? (Object.values(cleanupInfo.counts) as number[]).reduce((a, b) => a + b, 0)
    : 0

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
        <p className={styles.subtitle}>Server installation and maintenance</p>
      </header>

      {/* Installation */}
      <Card>
        <CardHeader
          title="Server Installation"
          subtitle="Install or update the DayZ server files via SteamCMD"
        />
        <div className={styles.actions}>
          <Button
            onClick={() => installOp.execute()}
            isLoading={installOp.isLoading}
            variant="secondary"
            icon={<Download size={16} />}
          >
            Install / Verify
          </Button>
          <Button
            onClick={() => updateOp.execute()}
            isLoading={updateOp.isLoading}
            variant="secondary"
            icon={<RefreshCw size={16} />}
          >
            Update Server
          </Button>
        </div>
        <p className={styles.hint}>
          <strong>Install/Verify</strong> downloads and validates all server files.
          <br />
          <strong>Update</strong> stops the server and downloads the latest version.
        </p>
      </Card>

      {/* Auto-Restart */}
      <Card>
        <CardHeader
          title="Auto-Restart"
          subtitle="Automatically restart the server if it crashes"
        />
        <div className={styles.toggleRow}>
          <div className={styles.toggleInfo}>
            <span className={styles.toggleLabel}>
              Auto-restart is currently{' '}
              <strong className={status?.auto_restart ? styles.enabled : styles.disabled}>
                {status?.auto_restart ? 'enabled' : 'disabled'}
              </strong>
            </span>
            <span className={styles.toggleHint}>
              Disable during maintenance or when testing mods
            </span>
          </div>
          {status?.auto_restart ? (
            <Button
              onClick={() => disableAutoRestartOp.execute()}
              isLoading={disableAutoRestartOp.isLoading}
              variant="secondary"
              icon={<ToggleRight size={18} />}
            >
              Disable
            </Button>
          ) : (
            <Button
              onClick={() => enableAutoRestartOp.execute()}
              isLoading={enableAutoRestartOp.isLoading}
              icon={<ToggleLeft size={18} />}
            >
              Enable
            </Button>
          )}
        </div>
      </Card>

      {/* Storage Management */}
      <Card>
        <CardHeader
          title="Storage Management"
          subtitle={`Persistence data for ${storageMap || 'current map'}`}
        />
        {storageDirs.length > 0 ? (
          <>
            <div className={styles.storageList}>
              {storageDirs.map(dir => (
                <div key={dir.name} className={styles.storageItem}>
                  <div className={styles.storageInfo}>
                    <HardDrive size={16} />
                    <span className={styles.storageName}>{dir.name}</span>
                    <span className={styles.storageSize}>{dir.size_human}</span>
                    <span className={styles.storageFiles}>{dir.file_count} files</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    onClick={() => handleWipeStorage(dir.name)}
                    isLoading={wipeStorageOp.isLoading}
                  >
                    Wipe
                  </Button>
                </div>
              ))}
            </div>
            <div className={styles.storageSummary}>
              <span>Total: {storageTotalSize}</span>
              <Button
                variant="secondary"
                size="sm"
                icon={<Trash2 size={14} />}
                onClick={() => handleWipeStorage()}
                isLoading={wipeStorageOp.isLoading}
              >
                Wipe All Storage
              </Button>
            </div>
          </>
        ) : (
          <p className={styles.hint}>
            No storage directories found. Start the server to create persistence data.
          </p>
        )}
        <div className={styles.warning}>
          <AlertTriangle size={16} />
          <span>
            Wiping storage deletes player inventories, bases, and vehicles. Server must be stopped.
          </span>
        </div>
      </Card>

      {/* Cleanup */}
      <Card>
        <CardHeader
          title="Server Files Cleanup"
          subtitle="Remove core dumps and temporary files from /serverfiles"
        />
        {totalCleanupItems > 0 ? (
          <>
            <div className={styles.cleanupSummary}>
              <FileX size={18} />
              <span>
                <strong>{totalCleanupItems}</strong> files can be cleaned up (
                {cleanupInfo?.total_size_human})
              </span>
            </div>
            <div className={styles.cleanupDetails}>
              {cleanupInfo && cleanupInfo.counts.core_dumps > 0 && (
                <span className={styles.cleanupItem}>
                  {cleanupInfo.counts.core_dumps} core dumps
                </span>
              )}
              {cleanupInfo && cleanupInfo.counts.crash_dumps > 0 && (
                <span className={styles.cleanupItem}>
                  {cleanupInfo.counts.crash_dumps} crash dumps
                </span>
              )}
              {cleanupInfo && cleanupInfo.counts.temp_files > 0 && (
                <span className={styles.cleanupItem}>
                  {cleanupInfo.counts.temp_files} temp files
                </span>
              )}
              {cleanupInfo && cleanupInfo.counts.log_files > 0 && (
                <span className={styles.cleanupItem}>
                  {cleanupInfo.counts.log_files} log files (not deleted by default)
                </span>
              )}
            </div>
            <div className={styles.actions}>
              <Button
                variant="secondary"
                icon={<Trash2 size={16} />}
                onClick={handleCleanup}
                isLoading={cleanupOp.isLoading}
              >
                Clean Up
              </Button>
              <Button variant="ghost" icon={<RefreshCw size={16} />} onClick={fetchCleanupInfo}>
                Refresh
              </Button>
            </div>
          </>
        ) : (
          <p className={styles.hint}>No files to clean up. Server files directory is clean.</p>
        )}
      </Card>

      {/* Steam */}
      <Card>
        <CardHeader
          title="Steam Login"
          subtitle="Required for downloading mods from the Workshop"
        />
        <div className={styles.steamInfo}>
          <div className={styles.steamStatus}>
            <Shield size={18} />
            <span>
              {steamStatus?.configured
                ? `Logged in as ${steamStatus.masked_username}`
                : 'Not configured'}
            </span>
          </div>
          <Button
            onClick={() => testSteamOp.execute()}
            isLoading={testSteamOp.isLoading}
            variant="secondary"
            size="sm"
          >
            Test Login
          </Button>
        </div>
        <p className={styles.hint}>
          To configure Steam login, run{' '}
          <code>docker compose exec api steamcmd +login YOUR_USERNAME</code>
          interactively, then call <code>POST /steam/login</code> with your username.
        </p>
      </Card>

      {/* Maintenance Mode */}
      <Card>
        <CardHeader
          title="Maintenance Mode"
          subtitle="Prevent server from auto-starting during updates and maintenance"
        />
        <div className={styles.toggleRow}>
          <div className={styles.toggleInfo}>
            <span className={styles.toggleLabel}>
              Maintenance mode is currently{' '}
              <strong className={status?.maintenance ? styles.disabled : styles.enabled}>
                {status?.maintenance ? 'enabled' : 'disabled'}
              </strong>
            </span>
            <span className={styles.toggleHint}>
              Blocks all auto-starts, auto-restarts, and manual start/restart commands
            </span>
          </div>
          {status?.maintenance ? (
            <Button
              onClick={() => disableMaintenanceOp.execute()}
              isLoading={disableMaintenanceOp.isLoading}
              icon={<ToggleRight size={18} />}
              variant="secondary"
            >
              Disable
            </Button>
          ) : (
            <Button
              onClick={() => enableMaintenanceOp.execute()}
              isLoading={enableMaintenanceOp.isLoading}
              icon={<ToggleLeft size={18} />}
            >
              Enable
            </Button>
          )}
        </div>
        <p className={styles.hint}>
          Maintenance mode stops the server and persists across container restarts. Use when
          performing server updates, mod installations, or configuration changes.
        </p>
      </Card>

      {/* Maintenance Tools */}
      {/* Info */}
      <Card>
        <CardHeader title="Server Info" />
        <div className={styles.infoGrid}>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Installed</span>
            <span className={styles.infoValue}>{status?.installed ? 'Yes' : 'No'}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Version</span>
            <span className={styles.infoValue}>{status?.version || '—'}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Map</span>
            <span className={styles.infoValue}>{status?.map || '—'}</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Restart Count</span>
            <span className={styles.infoValue}>{status?.restart_count ?? 0}</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
