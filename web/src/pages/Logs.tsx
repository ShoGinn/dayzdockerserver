import { LazyLog, ScrollFollow } from '@melloware/react-logviewer'
import { ChevronRight, FileText, Loader2, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import styles from './Logs.module.css'

interface LogFile {
  name: string
  path: string
  size_bytes: number
  size_human: string
  modified: string
  category: string
}

const CATEGORY_ORDER = ['crash', 'rpt', 'script', 'error', 'console', 'other'] as const
const CATEGORY_LABELS: Record<string, string> = {
  crash: 'Crash',
  rpt: 'RPT',
  script: 'Script',
  error: 'Error',
  console: 'Console',
  other: 'Other',
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function LogsPage() {
  const [files, setFiles] = useState<LogFile[]>([])
  const [selected, setSelected] = useState<string>('')
  const [content, setContent] = useState<string>('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [bytesCount, setBytesCount] = useState(20000)
  const [error, setError] = useState('')
  const [loadingFiles, setLoadingFiles] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [mobileOpen, setMobileOpen] = useState(false)
  const intervalRef = useRef<number | null>(null)

  const selectedFile = useMemo(() => files.find(f => f.name === selected), [files, selected])

  // Group files by category
  const grouped = useMemo(() => {
    const groups: Record<string, LogFile[]> = {}
    for (const cat of CATEGORY_ORDER) {
      const catFiles = files.filter(f => f.category === cat)
      if (catFiles.length > 0) groups[cat] = catFiles
    }
    return groups
  }, [files])

  // Find most recent file per category
  const mostRecentPerCategory = useMemo(() => {
    const result: Record<string, string> = {}
    for (const [cat, catFiles] of Object.entries(grouped)) {
      if (catFiles.length > 0) {
        result[cat] = catFiles[0].name // already sorted by modified desc
      }
    }
    return result
  }, [grouped])

  const loadFiles = useCallback(async () => {
    try {
      setLoadingFiles(true)
      const res = await api.listLogFiles()
      setFiles(res.files)
      // Auto-select the most recent file
      if (res.files.length > 0 && !selected) {
        setSelected(res.files[0].name)
      }
    } catch (e) {
      setError((e as { message?: string }).message ?? String(e))
    } finally {
      setLoadingFiles(false)
    }
  }, [selected])

  const loadTail = useCallback(async () => {
    if (!selected) return
    try {
      setLoadingContent(true)
      const res = await api.getLogTail(selected, bytesCount)
      setContent(res.content)
      setError('')
    } catch (e) {
      setError((e as { message?: string }).message ?? String(e))
    } finally {
      setLoadingContent(false)
    }
  }, [selected, bytesCount])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  useEffect(() => {
    loadTail()
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (autoRefresh && selected) {
      intervalRef.current = window.setInterval(loadTail, 2000)
    }
    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [loadTail, autoRefresh, selected])

  const toggleCategory = (cat: string) => {
    setCollapsed(prev => ({ ...prev, [cat]: !prev[cat] }))
  }

  const handleFileSelect = (name: string) => {
    setSelected(name)
    setContent('')
    setMobileOpen(false)
  }

  if (loadingFiles && files.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <Loader2 size={32} className="animate-spin" />
          Loading log files...
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Server Logs</h1>
        <p className={styles.subtitle}>View and tail server log files</p>
      </div>

      {/* Mobile toggle */}
      <button
        type="button"
        className={styles.mobileToggle}
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        <span>{selectedFile?.name ?? 'Select a log file'}</span>
        <ChevronRight
          size={16}
          className={`${styles.chevron} ${mobileOpen ? styles.chevronOpen : ''}`}
        />
      </button>

      <div className={styles.panels}>
        {/* File browser */}
        <Card
          padding="none"
          className={`${styles.browser} ${!mobileOpen ? styles.browserCollapsed : ''}`}
        >
          {Object.entries(grouped).map(([cat, catFiles]) => (
            <div key={cat} className={styles.categorySection}>
              <button
                type="button"
                className={styles.categoryHeader}
                onClick={() => toggleCategory(cat)}
              >
                <span
                  className={`${styles.categoryLeft} ${cat === 'crash' ? styles.categoryDanger : ''}`}
                >
                  <ChevronRight
                    size={14}
                    className={`${styles.chevron} ${!collapsed[cat] ? styles.chevronOpen : ''}`}
                  />
                  {CATEGORY_LABELS[cat] ?? cat}
                </span>
                <span className={styles.categoryCount}>{catFiles.length}</span>
              </button>
              {!collapsed[cat] && (
                <div className={styles.fileList}>
                  {catFiles.map(file => (
                    <button
                      key={file.name}
                      type="button"
                      className={`${styles.fileItem} ${selected === file.name ? styles.fileItemSelected : ''}`}
                      onClick={() => handleFileSelect(file.name)}
                    >
                      {mostRecentPerCategory[cat] === file.name ? (
                        <span className={styles.recentDot} />
                      ) : (
                        <span className={styles.recentDotHidden} />
                      )}
                      <span className={styles.fileInfo}>
                        <span className={styles.fileName} title={file.name}>
                          {file.name}
                        </span>
                        <span className={styles.fileMeta}>
                          {file.size_human} · {relativeTime(file.modified)}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {files.length === 0 && (
            <div className={styles.emptyState}>
              <FileText size={24} />
              No log files found
            </div>
          )}
        </Card>

        {/* Log viewer */}
        <Card padding="none" className={styles.viewer}>
          {selectedFile ? (
            <>
              <div className={styles.viewerHeader}>
                <div>
                  <h3 className={styles.viewerTitle}>{selectedFile.name}</h3>
                  <p className={styles.viewerMeta}>
                    {selectedFile.size_human} · {relativeTime(selectedFile.modified)}
                  </p>
                </div>
              </div>
              <div className={styles.controls}>
                <label className={styles.controlGroup}>
                  Tail bytes:
                  <input
                    type="number"
                    min={1000}
                    step={1000}
                    value={bytesCount}
                    onChange={e => setBytesCount(Number(e.target.value))}
                    className={styles.controlInput}
                  />
                </label>
                <label className={styles.controlGroup}>
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={e => setAutoRefresh(e.target.checked)}
                    className={styles.checkbox}
                  />
                  Auto-refresh
                </label>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<RefreshCw size={14} />}
                  isLoading={loadingContent}
                  onClick={loadTail}
                >
                  Refresh
                </Button>
              </div>
              <div className={styles.logContainer}>
                {error && <div className={styles.error}>Error: {error}</div>}
                {content ? (
                  <ScrollFollow
                    startFollowing={autoRefresh}
                    render={({ follow, onScroll }) => (
                      <LazyLog
                        text={content}
                        follow={follow}
                        onScroll={onScroll}
                        extraLines={1}
                        enableSearch
                        enableHotKeys
                        selectableLines
                        wrapLines
                        enableLinks
                        height="auto"
                        style={{
                          background: '#0b0d12',
                          color: '#cfe3ff',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '13px',
                        }}
                        containerStyle={{
                          overflow: 'auto',
                          maxHeight: 'calc(80vh - 200px)',
                          minHeight: '400px',
                        }}
                      />
                    )}
                  />
                ) : !error ? (
                  <div className={styles.emptyState}>
                    {loadingContent ? (
                      <>
                        <Loader2 size={24} className="animate-spin" />
                        Loading log content...
                      </>
                    ) : (
                      <>
                        <FileText size={24} />
                        No content
                      </>
                    )}
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <div className={styles.emptyState}>
              <FileText size={32} />
              Select a log file to view
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
