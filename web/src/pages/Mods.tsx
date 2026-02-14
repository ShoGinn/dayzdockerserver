import {
  AlertCircle,
  ExternalLink,
  Package,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card, CardHeader } from '../components/Card'
import { useToast } from '../components/Toast'
import { useOperation } from '../hooks/useOperation'
import type { ModInfo } from '../types'
import styles from './Mods.module.css'

export function ModsPage() {
  const [mods, setMods] = useState<ModInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newModId, setNewModId] = useState('')
  const { addToast } = useToast()

  const fetchMods = useCallback(async () => {
    try {
      const response = await api.getMods()
      setMods(response.mods)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load mods')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMods()
  }, [fetchMods])

  const installOp = useOperation(api.installMod, {
    onSuccess: () => {
      addToast('success', 'Mod installed successfully')
      setNewModId('')
      fetchMods()
    },
    onError: err => addToast('error', err),
  })

  const removeOp = useOperation(api.removeMod, {
    onSuccess: () => {
      addToast('success', 'Mod removed')
      fetchMods()
    },
    onError: err => addToast('error', err),
  })

  const activateOp = useOperation(api.activateMod, {
    onSuccess: () => {
      addToast('success', 'Mod activated')
      fetchMods()
    },
    onError: err => addToast('error', err),
  })

  const deactivateOp = useOperation(api.deactivateMod, {
    onSuccess: () => {
      addToast('success', 'Mod deactivated')
      fetchMods()
    },
    onError: err => addToast('error', err),
  })

  const updateAllOp = useOperation(api.updateAllMods, {
    onSuccess: res => {
      addToast('success', res.message)
      fetchMods()
    },
    onError: err => addToast('error', err),
  })

  const handleInstall = () => {
    const modId = newModId.trim()
    if (!modId) return

    // Extract mod ID from URL if needed
    const match = modId.match(/id=(\d+)/)
    const id = match ? match[1] : modId

    if (!/^\d+$/.test(id)) {
      addToast('error', 'Invalid mod ID. Enter a number or Steam Workshop URL.')
      return
    }

    installOp.execute(id)
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <RefreshCw className="animate-spin" size={32} />
        <span>Loading mods...</span>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Mods</h1>
          <p className={styles.subtitle}>Manage workshop mods for your server</p>
        </div>
        <Button
          onClick={() => updateAllOp.execute()}
          isLoading={updateAllOp.isLoading}
          variant="secondary"
          icon={<RefreshCw size={16} />}
        >
          Update All
        </Button>
      </header>

      {/* Install New Mod */}
      <Card>
        <CardHeader title="Install New Mod" subtitle="Paste a Workshop mod ID or URL" />
        <div className={styles.installForm}>
          <input
            type="text"
            value={newModId}
            onChange={e => setNewModId(e.target.value)}
            placeholder="e.g., 1559212036 or Workshop URL"
            className={styles.input}
            onKeyDown={e => e.key === 'Enter' && handleInstall()}
          />
          <Button onClick={handleInstall} isLoading={installOp.isLoading} icon={<Plus size={16} />}>
            Install
          </Button>
        </div>
      </Card>

      {error && (
        <div className={styles.error}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Mods List */}
      <Card padding="none">
        <div className={styles.modsHeader}>
          <span className={styles.modsCount}>
            <Package size={18} />
            {mods.length} mod{mods.length !== 1 ? 's' : ''} installed
          </span>
        </div>

        {mods.length === 0 ? (
          <div className={styles.empty}>
            <Package size={48} strokeWidth={1} />
            <p>No mods installed yet</p>
            <span>Install your first mod using the form above</span>
          </div>
        ) : (
          <div className={styles.modsList}>
            {mods.map(mod => (
              <div key={mod.id} className={`${styles.modItem} ${mod.active ? styles.active : ''}`}>
                <div className={styles.modInfo}>
                  <span className={styles.modName}>{mod.name || `Mod ${mod.id}`}</span>
                  <span className={styles.modMeta}>
                    ID: {mod.id} • {mod.size}
                  </span>
                </div>

                <div className={styles.modActions}>
                  <a
                    href={mod.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.modLink}
                    title="View on Steam Workshop"
                  >
                    <ExternalLink size={16} />
                  </a>

                  {mod.active ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deactivateOp.execute(mod.id)}
                      isLoading={deactivateOp.isLoading}
                      title="Deactivate mod"
                    >
                      <PowerOff size={16} />
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => activateOp.execute(mod.id)}
                      isLoading={activateOp.isLoading}
                      title="Activate mod"
                    >
                      <Power size={16} />
                    </Button>
                  )}

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (confirm(`Remove ${mod.name || mod.id}?`)) {
                        removeOp.execute(mod.id)
                      }
                    }}
                    isLoading={removeOp.isLoading}
                    title="Remove mod"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>

                {mod.active && <span className={styles.activeBadge}>Active</span>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
