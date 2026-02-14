import {
  AlertTriangle,
  Check,
  Download,
  ExternalLink,
  Globe,
  MapIcon,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { useToast } from '../components/Toast'
import styles from './Maps.module.css'

type MapInfo = {
  workshop_id: string
  name: string
  description: string
  templates: string[]
  default_template: string
  required_mods: string[]
  installed: boolean
  source: string
}

export function MapsPage() {
  const [maps, setMaps] = useState<MapInfo[]>([])
  const [installedTemplates, setInstalledTemplates] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [installingMap, setInstallingMap] = useState<string | null>(null)
  const { addToast } = useToast()

  const fetchMaps = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await api.getMaps()
      setMaps(response.maps)
      setInstalledTemplates(response.installed_templates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load maps')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMaps()
  }, [fetchMaps])

  const handleInstall = async (workshopId: string) => {
    try {
      setInstallingMap(workshopId)
      const response = await api.installMap(workshopId)
      addToast('success', response.message)
      await fetchMaps()
    } catch (err) {
      addToast('error', err instanceof Error ? err.message : 'Installation failed')
    } finally {
      setInstallingMap(null)
    }
  }

  const handleUninstall = async (workshopId: string, mapName: string) => {
    if (!confirm(`Remove ${mapName} mission files? This won't affect the workshop mod.`)) {
      return
    }

    try {
      setInstallingMap(workshopId)
      const response = await api.uninstallMap(workshopId)
      addToast('success', response.message)
      await fetchMaps()
    } catch (err) {
      addToast('error', err instanceof Error ? err.message : 'Uninstall failed')
    } finally {
      setInstallingMap(null)
    }
  }

  const isOfficial = (workshopId: string) => ['0', '1', '2'].includes(workshopId)

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <RefreshCw className="animate-spin" size={32} />
        <span>Loading maps...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.error}>
        <AlertTriangle size={32} />
        <span>{error}</span>
        <Button onClick={fetchMaps} variant="secondary">
          Try Again
        </Button>
      </div>
    )
  }

  const officialMaps = maps.filter(m => isOfficial(m.workshop_id))
  const communityMaps = maps.filter(m => !isOfficial(m.workshop_id))

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Maps</h1>
          <p className={styles.subtitle}>Install and manage custom maps</p>
        </div>
        <Button onClick={fetchMaps} variant="secondary" icon={<RefreshCw size={16} />}>
          Refresh
        </Button>
      </header>

      {/* Info */}
      <div className={styles.info}>
        <Globe size={18} />
        <div>
          <strong>How custom maps work:</strong> Install the workshop mod first (via Mods page),
          then install mission files here. Finally, update your server config to use the new map
          template.
        </div>
      </div>

      {/* Installed Templates */}
      {installedTemplates.length > 0 && (
        <Card className={styles.templatesCard}>
          <div className={styles.templatesHeader}>
            <MapIcon size={18} />
            <span>Installed Mission Templates</span>
          </div>
          <div className={styles.templatesList}>
            {installedTemplates.map(template => (
              <code key={template} className={styles.template}>
                {template}
              </code>
            ))}
          </div>
          <p className={styles.templatesHelp}>
            Use one of these in your server config&apos;s <code>template</code> setting
          </p>
        </Card>
      )}

      {/* Official Maps */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Official Maps</h2>
        <div className={styles.mapGrid}>
          {officialMaps.map(map => (
            <Card key={map.workshop_id} className={styles.mapCard}>
              <div className={styles.mapHeader}>
                <h3 className={styles.mapName}>{map.name}</h3>
                <span className={styles.badgeOfficial}>Official</span>
              </div>
              <p className={styles.mapDescription}>{map.description}</p>
              <div className={styles.mapTemplates}>
                <span className={styles.templatesLabel}>Templates:</span>
                {map.templates.map(t => (
                  <code key={t} className={styles.templateCode}>
                    {t}
                  </code>
                ))}
              </div>
              <div className={styles.mapActions}>
                <span className={styles.noAction}>Built into DayZ</span>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Community Maps */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Community Maps</h2>
        <div className={styles.mapGrid}>
          {communityMaps.map(map => (
            <Card key={map.workshop_id} className={styles.mapCard}>
              <div className={styles.mapHeader}>
                <h3 className={styles.mapName}>{map.name}</h3>
                {map.installed ? (
                  <span className={styles.badgeInstalled}>Installed</span>
                ) : (
                  <span className={styles.badgeNotInstalled}>Not Installed</span>
                )}
              </div>
              <p className={styles.mapDescription}>{map.description}</p>
              <div className={styles.mapTemplates}>
                <span className={styles.templatesLabel}>Templates:</span>
                {map.templates.map(t => (
                  <code key={t} className={styles.templateCode}>
                    {t}
                  </code>
                ))}
              </div>
              {map.required_mods.length > 0 && (
                <div className={styles.mapRequired}>
                  <AlertTriangle size={14} />
                  <span>Requires additional mods: {map.required_mods.join(', ')}</span>
                </div>
              )}
              <div className={styles.mapActions}>
                {map.installed ? (
                  <>
                    <Button variant="ghost" size="sm" icon={<Check size={14} />} disabled>
                      Installed
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Trash2 size={14} />}
                      onClick={() => handleUninstall(map.workshop_id, map.name)}
                      isLoading={installingMap === map.workshop_id}
                    >
                      Remove
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<Download size={14} />}
                    onClick={() => handleInstall(map.workshop_id)}
                    isLoading={installingMap === map.workshop_id}
                  >
                    Install Mission Files
                  </Button>
                )}
                <a
                  href={`https://steamcommunity.com/sharedfiles/filedetails/?id=${map.workshop_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.workshopLink}
                >
                  <ExternalLink size={14} />
                  Workshop
                </a>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Help */}
      <Card className={styles.helpCard}>
        <h3 className={styles.helpTitle}>Installation Steps</h3>
        <ol className={styles.helpSteps}>
          <li>
            <strong>Install the workshop mod</strong> - Go to the Mods page and install the
            map&apos;s workshop mod (e.g., &quot;Namalsk Island&quot; for Namalsk,
            &quot;DeerIsle&quot; for Deer Isle)
          </li>
          <li>
            <strong>Install mission files</strong> - Click &quot;Install Mission Files&quot; above
            to download the required mpmissions from GitHub
          </li>
          <li>
            <strong>Update server config</strong> - Go to Config page and change the{' '}
            <code>template</code>
            setting to the map&apos;s mission template (e.g., <code>regular.namalsk</code>)
          </li>
          <li>
            <strong>Restart server</strong> - The map will load on next server start
          </li>
        </ol>
      </Card>
    </div>
  )
}
