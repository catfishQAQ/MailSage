import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '../store/uiStore'
import type { AIStatusEvent } from '../types'

/**
 * 订阅后端 SSE AI 事件流，将更新写入 Zustand store 并使相关 Query cache 失效。
 */
export function useAIStream() {
  const applyAIUpdate = useUIStore((s) => s.applyAIUpdate)
  const queryClient = useQueryClient()

  useEffect(() => {
    const es = new EventSource('/api/ai/stream')

    es.addEventListener('ai_update', (e) => {
      try {
        const event: AIStatusEvent = JSON.parse(e.data)
        applyAIUpdate(event)
        // 使邮件详情缓存失效（如果当前打开的正好是这封）
        queryClient.invalidateQueries({ queryKey: ['email', event.email_id] })
        // 当完成时使列表缓存失效以更新计数
        if (event.ai_status === 'completed' || event.ai_status === 'failed') {
          queryClient.invalidateQueries({ queryKey: ['emails'] })
          queryClient.invalidateQueries({ queryKey: ['pending-count'] })
        }
      } catch (_) {}
    })

    es.onerror = () => {
      // SSE 断开后浏览器会自动重连
    }

    return () => es.close()
  }, [applyAIUpdate, queryClient])
}
