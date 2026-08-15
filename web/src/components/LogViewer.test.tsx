import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  clampTailBytes,
  findMatchingLines,
  isNearBottom,
  LogViewer,
  MAX_LOG_TAIL_BYTES,
} from './LogViewer'

describe('LogViewer helpers', () => {
  it('confines tail sizes to the API contract', () => {
    expect(clampTailBytes(-1)).toBe(1)
    expect(clampTailBytes(Number.NaN)).toBe(20000)
    expect(clampTailBytes(MAX_LOG_TAIL_BYTES + 1)).toBe(MAX_LOG_TAIL_BYTES)
  })

  it('finds matching lines case-insensitively', () => {
    expect(findMatchingLines(['Ready', 'warning', 'READY'], 'ready')).toEqual([0, 2])
  })

  it('detects whether the viewport is following the bottom', () => {
    expect(isNearBottom(476, 500, 1000)).toBe(true)
    expect(isNearBottom(100, 500, 1000)).toBe(false)
  })
})

describe('LogViewer', () => {
  it('renders line numbers and navigates search matches', async () => {
    const user = userEvent.setup()
    render(<LogViewer content={'Ready\nwarning\nREADY'} follow={false} />)

    expect(screen.queryByText('1')).not.toBeNull()
    expect(screen.queryByText('3')).not.toBeNull()
    await user.type(screen.getByRole('searchbox', { name: 'Search log' }), 'ready')
    expect(screen.queryByText('1/2')).not.toBeNull()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.queryByText('2/2')).not.toBeNull()
  })

  it('toggles wrapping and restores follow mode at the bottom', async () => {
    const user = userEvent.setup()
    render(<LogViewer content="line" follow />)

    const wrap = screen.getByRole('button', { name: 'Wrap' })
    expect(wrap.getAttribute('aria-pressed')).toBe('true')
    await user.click(wrap)
    expect(wrap.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(screen.getByRole('button', { name: 'Bottom' }))
  })

  it('renders empty content and updates when a refreshed tail arrives', () => {
    const { rerender } = render(<LogViewer content="" follow />)

    expect(screen.queryByText('1')).not.toBeNull()
    rerender(<LogViewer content={'first\nsecond'} follow />)
    expect(screen.queryByText('second')).not.toBeNull()
    expect(screen.queryByText('2')).not.toBeNull()
  })
})
