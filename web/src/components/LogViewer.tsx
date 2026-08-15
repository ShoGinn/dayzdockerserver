import { useEffect, useMemo, useRef, useState } from 'react'
import styles from './LogViewer.module.css'

export const MAX_LOG_TAIL_BYTES = 512 * 1024
export const MIN_LOG_TAIL_BYTES = 1

export function clampTailBytes(value: number): number {
  if (!Number.isFinite(value)) return 20000
  return Math.min(MAX_LOG_TAIL_BYTES, Math.max(MIN_LOG_TAIL_BYTES, Math.trunc(value)))
}

export function findMatchingLines(lines: string[], query: string): number[] {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery) return []
  return lines.flatMap((line, index) =>
    line.toLocaleLowerCase().includes(normalizedQuery) ? [index] : []
  )
}

export function isNearBottom(
  scrollTop: number,
  clientHeight: number,
  scrollHeight: number
): boolean {
  return scrollHeight - scrollTop - clientHeight <= 24
}

interface LogViewerProps {
  content: string
  follow: boolean
}

function HighlightedLine({ line, query }: { line: string; query: string }) {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery) return <>{line || ' '}</>

  const parts: Array<{ text: string; match: boolean; offset: number }> = []
  const normalizedLine = line.toLocaleLowerCase()
  let cursor = 0
  while (cursor < line.length) {
    const matchIndex = normalizedLine.indexOf(normalizedQuery, cursor)
    if (matchIndex < 0) {
      parts.push({ text: line.slice(cursor), match: false, offset: cursor })
      break
    }
    if (matchIndex > cursor) {
      parts.push({ text: line.slice(cursor, matchIndex), match: false, offset: cursor })
    }
    parts.push({
      text: line.slice(matchIndex, matchIndex + normalizedQuery.length),
      match: true,
      offset: matchIndex,
    })
    cursor = matchIndex + normalizedQuery.length
  }

  return (
    <>
      {parts.map(part =>
        part.match ? <mark key={`${part.offset}-${part.text}`}>{part.text}</mark> : part.text
      )}
    </>
  )
}

export function LogViewer({ content, follow }: LogViewerProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const activeLineRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [activeMatch, setActiveMatch] = useState(0)
  const [wrapLines, setWrapLines] = useState(true)
  const [following, setFollowing] = useState(true)
  const lineEntries = useMemo(() => {
    let offset = 0
    return content.split(/\r?\n/).map(line => {
      const entry = { id: offset, line }
      offset += line.length + 1
      return entry
    })
  }, [content])
  const lines = useMemo(() => lineEntries.map(entry => entry.line), [lineEntries])
  const matches = useMemo(() => findMatchingLines(lines, query), [lines, query])
  const activeLine = matches[activeMatch]

  useEffect(() => {
    if (activeMatch >= matches.length) setActiveMatch(0)
  }, [activeMatch, matches.length])

  useEffect(() => {
    if (lineEntries.length > 0 && follow && following) {
      const viewport = viewportRef.current
      if (viewport) viewport.scrollTop = viewport.scrollHeight
    }
  }, [lineEntries, follow, following])

  useEffect(() => {
    if (activeLine !== undefined) {
      activeLineRef.current?.scrollIntoView?.({ block: 'center' })
    }
  }, [activeLine])

  const moveMatch = (offset: number) => {
    if (matches.length === 0) return
    setActiveMatch(current => (current + offset + matches.length) % matches.length)
    setFollowing(false)
  }

  const scrollToBottom = () => {
    const viewport = viewportRef.current
    if (viewport) viewport.scrollTop = viewport.scrollHeight
    setFollowing(true)
  }

  return (
    <div className={styles.viewer}>
      <div className={styles.toolbar}>
        <label className={styles.searchLabel}>
          <input
            type="search"
            aria-label="Search log"
            value={query}
            onChange={event => {
              setQuery(event.target.value)
              setActiveMatch(0)
            }}
            placeholder="Search log"
            className={styles.searchInput}
          />
        </label>
        <span className={styles.matchCount} aria-live="polite">
          {matches.length > 0 ? `${activeMatch + 1}/${matches.length}` : '0/0'}
        </span>
        <button type="button" onClick={() => moveMatch(-1)} disabled={matches.length === 0}>
          Previous
        </button>
        <button type="button" onClick={() => moveMatch(1)} disabled={matches.length === 0}>
          Next
        </button>
        <button
          type="button"
          aria-pressed={wrapLines}
          onClick={() => setWrapLines(current => !current)}
        >
          Wrap
        </button>
        <button type="button" onClick={scrollToBottom}>
          Bottom
        </button>
      </div>
      <div
        ref={viewportRef}
        data-testid="log-viewport"
        className={styles.viewport}
        onScroll={event => {
          const target = event.currentTarget
          setFollowing(isNearBottom(target.scrollTop, target.clientHeight, target.scrollHeight))
        }}
      >
        <div className={`${styles.lines} ${wrapLines ? styles.wrapped : styles.unwrapped}`}>
          {lineEntries.map(({ id, line }, index) => {
            const isActive = index === activeLine
            return (
              <div
                key={id}
                ref={isActive ? activeLineRef : undefined}
                className={`${styles.line} ${isActive ? styles.activeLine : ''}`}
                aria-current={isActive ? 'true' : undefined}
              >
                <span className={styles.lineNumber} aria-hidden="true">
                  {index + 1}
                </span>
                <code className={styles.lineContent}>
                  <HighlightedLine line={line} query={query} />
                </code>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
