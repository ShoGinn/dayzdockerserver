import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Code,
  FileText,
  Info,
  RefreshCw,
  Save,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { useToast } from '../components/Toast'
import { useOperation } from '../hooks/useOperation'
import styles from './Config.module.css'

type FieldInfo = {
  type: string
  default: unknown
  description: string | null
}

type ConfigSchema = {
  fields: Record<string, FieldInfo>
  sections: Record<string, string[]>
  descriptions: Record<string, string>
}

type ConfigData = Record<string, unknown>

export function ConfigPage() {
  const [mode, setMode] = useState<'form' | 'raw'>('form')
  const [config, setConfig] = useState<ConfigData>({})
  const [originalConfig, setOriginalConfig] = useState<ConfigData>({})
  const [schema, setSchema] = useState<ConfigSchema | null>(null)
  const [rawConfig, setRawConfig] = useState('')
  const [originalRawConfig, setOriginalRawConfig] = useState('')
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['Server Identity', 'Gameplay'])
  )
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { addToast } = useToast()

  const hasChanges =
    mode === 'form'
      ? JSON.stringify(config) !== JSON.stringify(originalConfig)
      : rawConfig !== originalRawConfig

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // Fetch schema and config in parallel
      const [schemaRes, configRes, rawRes] = await Promise.all([
        api.getConfigSchema(),
        api.getStructuredConfig(),
        api.getConfig(true),
      ])

      setSchema(schemaRes)
      setConfig(configRes.data)
      setOriginalConfig(configRes.data)
      setRawConfig(rawRes.content)
      setOriginalRawConfig(rawRes.content)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load config')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const saveFormOp = useOperation(api.updateStructuredConfig, {
    onSuccess: () => {
      addToast('success', 'Config saved! Restart the server to apply changes.')
      setOriginalConfig({ ...config })
      // Also refresh raw config to stay in sync
      api.getConfig(true).then(res => {
        setRawConfig(res.content)
        setOriginalRawConfig(res.content)
      })
    },
    onError: err => addToast('error', err),
  })

  const saveRawOp = useOperation(api.updateConfig, {
    onSuccess: () => {
      addToast('success', 'Config saved! Restart the server to apply changes.')
      setOriginalRawConfig(rawConfig)
      // Refresh structured config to stay in sync
      api.getStructuredConfig().then(res => {
        setConfig(res.data)
        setOriginalConfig(res.data)
      })
    },
    onError: err => addToast('error', err),
  })

  const handleSaveForm = () => {
    saveFormOp.execute(config)
  }

  const handleSaveRaw = () => {
    saveRawOp.execute(rawConfig)
  }

  const handleReset = () => {
    if (confirm('Discard all changes?')) {
      if (mode === 'form') {
        setConfig({ ...originalConfig })
      } else {
        setRawConfig(originalRawConfig)
      }
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const updateField = (key: string, value: unknown) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  const renderField = (key: string, fieldInfo: FieldInfo) => {
    const value = config[key]
    const description = fieldInfo.description || schema?.descriptions[key]

    // Determine input type based on field type and key
    const isPassword = key.toLowerCase().includes('password')
    const isBooleanLike =
      fieldInfo.type === 'int' &&
      (key.startsWith('disable') ||
        key.startsWith('enable') ||
        key === 'forceSameBuild' ||
        key === 'serverTimePersistent' ||
        key === 'storageAutoFix' ||
        key === 'storeHouseStateDisabled' ||
        key === 'adminLogPlayerHitsOnly' ||
        key === 'adminLogPlacement' ||
        key === 'adminLogBuildActions' ||
        key === 'adminLogPlayerList' ||
        key === 'logAverageFps' ||
        key === 'logMemory' ||
        key === 'logPlayers' ||
        key === 'multithreadedReplication' ||
        key === 'speedhackDetection')

    return (
      <div key={key} className={styles.field}>
        <div className={styles.fieldHeader}>
          <label className={styles.fieldLabel} htmlFor={key}>
            {key}
          </label>
          {description && (
            <span className={styles.fieldDescription} title={description}>
              <Info size={14} />
              <span>{description}</span>
            </span>
          )}
        </div>
        <div className={styles.fieldInput}>
          {fieldInfo.type === 'list' ? (
            <textarea
              id={key}
              value={Array.isArray(value) ? value.join('\n') : ''}
              onChange={e => updateField(key, e.target.value.split('\n').filter(Boolean))}
              className={styles.textarea}
              rows={3}
              placeholder="One item per line"
            />
          ) : isBooleanLike ? (
            <select
              id={key}
              value={Number(value) || 0}
              onChange={e => updateField(key, parseInt(e.target.value, 10))}
              className={styles.select}
            >
              <option value={0}>Disabled (0)</option>
              <option value={1}>Enabled (1)</option>
            </select>
          ) : fieldInfo.type === 'int' ? (
            <input
              id={key}
              type="number"
              value={(value as number) ?? fieldInfo.default ?? 0}
              onChange={e => updateField(key, parseInt(e.target.value, 10) || 0)}
              className={styles.input}
            />
          ) : fieldInfo.type === 'float' ? (
            <input
              id={key}
              type="number"
              step="0.1"
              value={(value as number) ?? fieldInfo.default ?? 0}
              onChange={e => updateField(key, parseFloat(e.target.value) || 0)}
              className={styles.input}
            />
          ) : (
            <input
              id={key}
              type={isPassword ? 'password' : 'text'}
              value={(value as string) ?? ''}
              onChange={e => updateField(key, e.target.value)}
              className={styles.input}
              placeholder={(fieldInfo.default as string) || ''}
            />
          )}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <RefreshCw className="animate-spin" size={32} />
        <span>Loading config...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.error}>
        <AlertTriangle size={32} />
        <span>{error}</span>
        <Button onClick={fetchData} variant="secondary">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Server Config</h1>
          <p className={styles.subtitle}>
            {mode === 'form' ? 'Edit settings by category' : 'Edit serverDZ.cfg directly'}
          </p>
        </div>
        <div className={styles.headerActions}>
          <div className={styles.modeToggle}>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === 'form' ? styles.active : ''}`}
              onClick={() => setMode('form')}
            >
              Form
            </button>
            <button
              type="button"
              className={`${styles.modeButton} ${mode === 'raw' ? styles.active : ''}`}
              onClick={() => setMode('raw')}
            >
              <Code size={14} />
              Raw
            </button>
          </div>
          {hasChanges && (
            <Button onClick={handleReset} variant="ghost">
              Discard
            </Button>
          )}
          <Button
            onClick={mode === 'form' ? handleSaveForm : handleSaveRaw}
            isLoading={mode === 'form' ? saveFormOp.isLoading : saveRawOp.isLoading}
            disabled={!hasChanges}
            icon={<Save size={16} />}
          >
            Save Changes
          </Button>
        </div>
      </header>

      {hasChanges && (
        <div className={styles.warning}>
          <AlertTriangle size={18} />
          <div>
            <strong>Unsaved changes!</strong> Don&apos;t forget to save and restart the server.
          </div>
        </div>
      )}

      {mode === 'form' && schema ? (
        <div className={styles.sections}>
          {Object.entries(schema.sections).map(([sectionName, fields]) => {
            const isExpanded = expandedSections.has(sectionName)
            const sectionFields = fields.filter(f => schema.fields[f])
            if (sectionFields.length === 0) return null

            return (
              <Card key={sectionName} padding="none" className={styles.section}>
                <button
                  type="button"
                  className={styles.sectionHeader}
                  onClick={() => toggleSection(sectionName)}
                >
                  {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  <span className={styles.sectionTitle}>{sectionName}</span>
                  <span className={styles.sectionCount}>{sectionFields.length} settings</span>
                </button>
                {isExpanded && (
                  <div className={styles.sectionContent}>
                    {sectionFields.map(fieldKey => renderField(fieldKey, schema.fields[fieldKey]))}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      ) : (
        <Card padding="none" className={styles.editorCard}>
          <div className={styles.editorHeader}>
            <FileText size={16} />
            <span>serverDZ.cfg</span>
            {hasChanges && <span className={styles.unsaved}>Unsaved changes</span>}
          </div>
          <textarea
            value={rawConfig}
            onChange={e => setRawConfig(e.target.value)}
            className={styles.editor}
            spellCheck={false}
          />
        </Card>
      )}
    </div>
  )
}
