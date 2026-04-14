import { create } from 'zustand'
import type { AIStatusEvent, EmailListItem, MailboxView } from '../types'

interface UIState {
  selectedItemId: string | null
  selectedAccountId: string | null
  selectedView: MailboxView
  aiUpdates: Record<string, AIStatusEvent>

  setSelectedItem: (id: string | null) => void
  setAccountView: (accountId: string, view: MailboxView) => void
  setSelectedAccount: (id: string | null) => void
  applyAIUpdate: (event: AIStatusEvent) => void
}

export const useUIStore = create<UIState>((set) => ({
  selectedItemId: null,
  selectedAccountId: null,
  selectedView: 'all',
  aiUpdates: {},

  setSelectedItem: (id) =>
    set((state) => (state.selectedItemId === id ? state : { selectedItemId: id })),
  setAccountView: (accountId, view) =>
    set((state) => {
      const nextSelectedItemId =
        state.selectedAccountId === accountId && state.selectedView === view ? state.selectedItemId : null
      if (
        state.selectedAccountId === accountId &&
        state.selectedView === view &&
        state.selectedItemId === nextSelectedItemId
      ) {
        return state
      }
      return {
        selectedAccountId: accountId,
        selectedView: view,
        selectedItemId: nextSelectedItemId,
      }
    }),
  setSelectedAccount: (id) =>
    set((state) => {
      const nextView = id && state.selectedAccountId === id ? state.selectedView : 'all'
      if (
        state.selectedAccountId === id &&
        state.selectedView === nextView &&
        state.selectedItemId === null
      ) {
        return state
      }
      return {
        selectedAccountId: id,
        selectedView: nextView,
        selectedItemId: null,
      }
    }),
  applyAIUpdate: (event) =>
    set((state) => ({
      aiUpdates: { ...state.aiUpdates, [event.email_id]: event },
    })),
}))

export function mergeAIUpdate(
  item: EmailListItem,
  updates: Record<string, AIStatusEvent>,
): EmailListItem {
  const u = updates[item.id]
  if (!u) return item
  return {
    ...item,
    ai_status: u.ai_status,
    ai_importance: u.ai_importance ?? item.ai_importance,
    ai_is_important: u.ai_is_important ?? item.ai_is_important,
    ai_summary: u.ai_summary ?? item.ai_summary,
  }
}
