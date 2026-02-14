import {
  AlertCircle,
  ExternalLink,
  Package,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Shield,
  Trash2,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card, CardHeader } from '../components/Card'
import { useToast } from '../components/Toast'
import { useOperation } from '../hooks/useOperation'
import type { ModInfo } from '../types'
import styles from './Mods.module.css'

const VPP_MOD_ID = '1828439124'

export function ModsPage() {
  const [mods, setMods] = useState<ModInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newModId, setNewModId] = useState('')
  const [vppInstalled, setVppInstalled] = useState(false)
  const [vppSuperadmins, setVppSuperadmins] = useState<string[]>([])
  const [vppLoading, setVppLoading] = useState(false)
  const [newSuperadminId, setNewSuperadminId] = useState('')
  const { addToast } = useToast()

  const fetchMods = useCallback(async () => {
    try {
      const response = await api.getMods()
      setMods(response.mods)
      setVppInstalled(response.mods.some(m => m.id === VPP_MOD_ID))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load mods')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchVppSuperadmins = useCallback(async () => {
    if (!vppInstalled) return
    try {
      setVppLoading(true)
      const response = await api.getVppSuperadmins()
      setVppSuperadmins(response.steam64_ids)
    } catch (err) {
      console.error('Failed to load VPP superadmins:', err)
      // Silently fail - VPP might not be fully configured
    } finally {
      setVppLoading(false)
    }
  }, [vppInstalled])

  useEffect(() => {
    fetchMods()
  }, [fetchMods])

  useEffect(() => {
    fetchVppSuperadmins()
  }, [fetchVppSuperadmins])

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

  const setVppSuperadminsOp = useOperation(api.setVppSuperadmins, {
    onSuccess: () => {
      addToast('success', 'Superadmins updated')
      fetchVppSuperadmins()
      setNewSuperadminId('')
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

  const handleAddSuperadmin = () => {
    const id = newSuperadminId.trim()
    if (!id) return

    if (!/^\d+$/.test(id)) {
      addToast('error', 'Invalid Steam64 ID. Must be a number.')
      return
    }

    if (vppSuperadmins.includes(id)) {
      addToast('error', 'This Steam64 ID is already a superadmin')
      return
    }

    const updated = [...vppSuperadmins, id]
    setVppSuperadminsOp.execute(updated, 'overwrite')
  }

  const handleRemoveSuperadmin = (id: string) => {
    const updated = vppSuperadmins.filter(existing => existing !== id)
    setVppSuperadminsOp.execute(updated, 'overwrite')
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

      {/* VPP Admin Tools Settings */}
      {vppInstalled && (
        <Card>
          <CardHeader
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={20} />
                VPP Admin Tools
              </div>
            }
            subtitle="Manage server administrators"
          />
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Superadmins Section */}
            <div>
              <h3 style={{ marginBottom: '8px', fontSize: '14px', fontWeight: '600' }}>
                Superadmins
              </h3>

              {/* Add New Superadmin */}
              <div
                style={{
                  display: 'flex',
                  gap: '8px',
                  marginBottom: '12px',
                }}
              >
                <input
                  type="text"
                  value={newSuperadminId}
                  onChange={e => setNewSuperadminId(e.target.value)}
                  placeholder="Enter Steam64 ID"
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    fontSize: '14px',
                  }}
                  onKeyDown={e => e.key === 'Enter' && handleAddSuperadmin()}
                />
                <Button
                  onClick={handleAddSuperadmin}
                  isLoading={setVppSuperadminsOp.isLoading}
                  icon={<Plus size={16} />}
                  size="sm"
                >
                  Add
                </Button>
              </div>

              {/* Superadmins List */}
              {vppLoading ? (
                <div style={{ textAlign: 'center', padding: '16px', color: '#666' }}>
                  <RefreshCw size={16} className="animate-spin" />
                </div>
              ) : vppSuperadmins.length === 0 ? (
                <div style={{ padding: '12px', textAlign: 'center', color: '#999' }}>
                  No superadmins configured
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0px',
                  }}
                >
                  {vppSuperadmins.map((id, index) => (
                    <div
                      key={id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 16px',
                        backgroundColor: 'var(--bg-secondary)',
                        borderBottom:
                          index < vppSuperadmins.length - 1
                            ? '1px solid var(--border-color)'
                            : 'none',
                        fontSize: '14px',
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      <span>{id}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveSuperadmin(id)}
                        isLoading={setVppSuperadminsOp.isLoading}
                        title="Remove superadmin"
                      >
                        <X size={16} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
