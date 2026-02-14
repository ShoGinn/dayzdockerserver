import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'

export function LogsPage() {
  const [files, setFiles] = useState<Array<{ name: string; path: string }>>([])
  const [selected, setSelected] = useState<string>('')
  const [content, setContent] = useState<string>('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [bytesCount, setBytesCount] = useState(20000)
  const intervalRef = useRef<number | null>(null)
  const [error, setError] = useState<string>('')

  const filename = useMemo(() => selected || (files[0]?.name ?? ''), [selected, files])

  const loadFiles = useCallback(async (): Promise<void> => {
    try {
      const res = await api.listLogFiles()
      setFiles(res.files.map(f => ({ name: f.name, path: f.path })))
    } catch (e) {
      const err = e as { message?: string }
      setError(err.message ?? String(e))
    }
  }, [])

  const loadTail = useCallback(async (): Promise<void> => {
    if (!filename) return
    try {
      const res = await api.getLogTail(filename, bytesCount)
      setContent(res.content)
      setError('')
    } catch (e) {
      const err = e as { message?: string }
      setError(err.message ?? String(e))
    }
  }, [filename, bytesCount])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  useEffect(() => {
    loadTail()
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (autoRefresh) {
      intervalRef.current = window.setInterval(loadTail, 1000)
    }
    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [loadTail, autoRefresh])

  return (
    <div style={{ padding: '1rem' }}>
      <h1 style={{ marginBottom: '1rem' }}>Server Logs</h1>
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '0.5rem' }}>
        <label>
          File:
          <select
            value={filename}
            onChange={e => setSelected(e.target.value)}
            style={{ marginLeft: '0.5rem' }}
          >
            {files.map(f => (
              <option key={f.name} value={f.name}>
                {f.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tail bytes:
          <input
            type="number"
            min={1000}
            step={1000}
            value={bytesCount}
            onChange={e => setBytesCount(Number(e.target.value))}
            style={{ width: 100, marginLeft: '0.5rem' }}
          />
        </label>
        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={e => setAutoRefresh(e.target.checked)}
          />
          Auto-refresh
        </label>
        <button type="button" onClick={loadTail}>
          Refresh Now
        </button>
      </div>
      {error && <div style={{ color: 'crimson', marginBottom: '0.5rem' }}>Error: {error}</div>}
      <pre
        style={{
          background: '#0b0d12',
          color: '#cfe3ff',
          padding: '1rem',
          borderRadius: 8,
          whiteSpace: 'pre-wrap',
          maxHeight: '60vh',
          overflow: 'auto',
        }}
      >
        {content || 'No content.'}
      </pre>
    </div>
  )
}
