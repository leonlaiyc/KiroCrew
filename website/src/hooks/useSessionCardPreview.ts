import { useSyncExternalStore } from 'react'
import { loadChatConfig } from '../pages/chat/ChatSettings'

const sub = (cb: () => void) => { window.addEventListener('mc-config-changed', cb); return () => window.removeEventListener('mc-config-changed', cb) }
const get = () => loadChatConfig().sessionCardPreview !== false

/** Settings → Chat → Sessions → Message Preview on Session Cards, read live.
 *  Only an explicit `false` hides the line: the setting defaults to on. */
export const useSessionCardPreview = () => useSyncExternalStore(sub, get)
