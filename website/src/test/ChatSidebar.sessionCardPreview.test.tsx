/**
 * Settings → Chat → Sessions → Message Preview on Session Cards: with the
 * setting off, a sidebar session card drops its last-message line, so an idle
 * card is its title alone. What the line carries besides the preview stays:
 * the unread dot, and every status line (an owed approval, a running turn).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act, render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { createTestStore } from './helpers'
import { ThemeProvider } from '../hooks/useTheme'

// Render framer-motion elements as plain DOM (jsdom can't run projection).
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const FRAMER_PROPS = new Set([
    'layout', 'layoutId', 'layoutScroll', 'initial', 'animate', 'exit',
    'transition', 'variants', 'whileHover', 'whileTap', 'whileInView',
    'drag', 'dragConstraints', 'dragElastic', 'onAnimationComplete',
  ])
  const make = (tag: string) =>
    React.forwardRef((props: Record<string, unknown>, ref: React.Ref<unknown>) => {
      const clean: Record<string, unknown> = {}
      for (const k of Object.keys(props)) {
        if (k === 'children') continue
        if (k === 'layoutId') { clean['data-layout-id'] = props[k]; continue }
        if (FRAMER_PROPS.has(k)) continue
        clean[k] = props[k]
      }
      return React.createElement(tag, { ...clean, ref }, props.children as React.ReactNode)
    })
  const motion = new Proxy({}, { get: (_t, tag: string) => make(tag) })
  return {
    motion,
    AnimatePresence: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    LayoutGroup: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  }
})

vi.mock('../components/ProjectPicker', () => ({ default: () => null }))

// Mutable chat config: the row reads `sessionCardPreview` through
// useSessionCardPreview -> loadChatConfig. tagColumnsEnabled stays off so the
// rows render as one flat lane and stay easy to query.
const cfg = vi.hoisted(() => ({
  value: { tagColumnsEnabled: false, confirmCloseSession: false } as Record<string, unknown>,
}))
vi.mock('../pages/chat/ChatSettings', () => ({
  loadChatConfig: () => cfg.value,
  saveChatConfig: vi.fn(),
}))

vi.mock('../api/client', () => ({
  SEARCH_MIN_CHARS: 2,
  api: new Proxy({} as Record<string, unknown>, {
    get: () => vi.fn().mockResolvedValue([]),
  }),
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((q: string) => ({
    matches: false, media: q, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })),
})

globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) }) as unknown as typeof fetch

import ChatSidebar from '../pages/ChatSidebar'
import type { RootState } from '../store'
import type { ChatSlot } from '../types'


const UNREAD_DOT_TITLE = 'Agent finished — your turn'

/** Render, then let the providers' boot fetches (the theme catalog) land
 *  inside act, so no state update arrives after the test's last barrier. */
async function renderSidebar(slots: ChatSlot[], unreadSlots: string[] = []) {
  const view = renderNow(slots, unreadSlots)
  await act(async () => { await new Promise(r => setTimeout(r, 0)) })
  return view
}

function renderNow(slots: ChatSlot[], unreadSlots: string[] = []) {
  const store = createTestStore({
    dashboard: {
      status: {}, connected: true, slots, approvalMode: 'normal',
      channelTrusted: false, refreshTrigger: 0, unreadSlots, updateProgress: null,
      slotsLoaded: true,
      subagentRunning: {}, subagentDetails: {}, subagentText: {},
      sessionDefaultColor: null, sessionColorsMode: 'tint', sessionColorsPalette: 'horizon', sessionColorsIntensity: 'clear',
    } as unknown as RootState['dashboard'],
    chat: { activeSlot: null, slotStatusDetail: {}, subagents: {}, slotActivity: {}, automations: {} } as unknown as RootState['chat'],
  })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  qc.setQueryData(['chat-folders'], [])
  return render(
    <QueryClientProvider client={qc}>
      <Provider store={store}>
        <ThemeProvider>
          <MemoryRouter>
            <ChatSidebar
              slots={slots} activeSlot={null} unreadSlots={unreadSlots}
              history={[]} historyHasMore={false} defaultAgent="" installedAgents={[]}
            />
          </MemoryRouter>
        </ThemeProvider>
      </Provider>
    </QueryClientProvider>,
  )
}

const idle = (over: Record<string, unknown> = {}) =>
  [{ key: 'k', title: 'Release notes', running: false, messages: 5, last_message: 'Drafted the changelog', ...over }] as unknown as ChatSlot[]

beforeEach(() => {
  localStorage.clear()
  cfg.value = { tagColumnsEnabled: false, confirmCloseSession: false }
})
afterEach(() => { vi.clearAllMocks() })

describe('session card preview setting', () => {
  it('shows the last message when the setting was never set', async () => {
    const { getByText } = await renderSidebar(idle())
    expect(getByText('Release notes')).toBeTruthy()
    expect(getByText('Drafted the changelog')).toBeTruthy()
  })

  it('drops the last-message line when the setting is off', async () => {
    cfg.value = { ...cfg.value, sessionCardPreview: false }
    const { getByText, queryByText, queryByTestId } = await renderSidebar(idle())
    expect(getByText('Release notes')).toBeTruthy()
    expect(queryByText('Drafted the changelog')).toBeNull()
    expect(queryByTestId('session-card-preview')).toBeNull()
  })

  it('keeps the unread dot when the setting is off', async () => {
    cfg.value = { ...cfg.value, sessionCardPreview: false }
    const { queryByTitle, queryByText } = await renderSidebar(idle(), ['k'])
    expect(queryByTitle(UNREAD_DOT_TITLE)).toBeTruthy()
    expect(queryByText('Drafted the changelog')).toBeNull()
  })

  it('keeps an owed approval on the card when the setting is off', async () => {
    cfg.value = { ...cfg.value, sessionCardPreview: false }
    const { getByText } = await renderSidebar(idle({ pending_approval: true }))
    expect(getByText('Needs approval')).toBeTruthy()
  })

  it('follows a change made in Settings without a reload', async () => {
    const { queryByText } = await renderSidebar(idle())
    expect(queryByText('Drafted the changelog')).toBeTruthy()
    act(() => {
      cfg.value = { ...cfg.value, sessionCardPreview: false }
      window.dispatchEvent(new Event('mc-config-changed'))
    })
    expect(queryByText('Drafted the changelog')).toBeNull()
    act(() => {
      cfg.value = { ...cfg.value, sessionCardPreview: true }
      window.dispatchEvent(new Event('mc-config-changed'))
    })
    expect(queryByText('Drafted the changelog')).toBeTruthy()
  })
})

describe('sessionCardPreview in the stored chat config', () => {
  it('defaults to on, keeps a stored off, and ignores a non-boolean', async () => {
    const actual = await vi.importActual<typeof import('../pages/chat/ChatSettings')>('../pages/chat/ChatSettings')
    const key = 'mc-chat-config'
    expect(actual.loadChatConfig().sessionCardPreview).toBe(true)
    localStorage.setItem(key, JSON.stringify({ sessionCardPreview: false }))
    expect(actual.loadChatConfig().sessionCardPreview).toBe(false)
    localStorage.setItem(key, JSON.stringify({ sessionCardPreview: 'no' }))
    expect(actual.loadChatConfig().sessionCardPreview).toBe(true)
  })
})
