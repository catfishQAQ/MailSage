import { create } from 'zustand'
import type { AIStatusEvent, EmailListItem } from '../types'

interface UIState {
  selectedEmailId: string | null
  selectedAccountId: string | null
  filterImportant: boolean
  // AI 状态事件缓存（从 SSE 实时更新，用于无需重新请求列表即可刷新 AI 字段）
  aiUpdates: Record<string, AIStatusEvent>

  setSelectedEmail: (id: string | null) => void
  setSelectedAccount: (id: string | null) => void
  setFilterImportant: (v: boolean) => void
  applyAIUpdate: (event: AIStatusEvent) => void
}

export const useUIStore = create<UIState>((set) => ({
  selectedEmailId: null,
  selectedAccountId: null,
  filterImportant: false,
  aiUpdates: {},

  setSelectedEmail: (id) => set({ selectedEmailId: id }),
  setSelectedAccount: (id) => set({ selectedAccountId: id }),
  setFilterImportant: (v) => set({ filterImportant: v }),
  applyAIUpdate: (event) =>
    set((state) => ({
      aiUpdates: { ...state.aiUpdates, [event.email_id]: event },
    })),
}))

/** 将 SSE AI 更新与列表项合并 */
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
