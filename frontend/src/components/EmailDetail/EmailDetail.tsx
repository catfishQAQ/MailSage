import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useEmailDetail, useTriggerOneEmail } from '../../hooks/useEmails'
import { useUIStore } from '../../store/uiStore'
import { SummaryCard } from './SummaryCard'
import { GhostReplyEditor } from '../ReplyEditor/GhostReplyEditor'

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'Z')
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function EmailDetail() {
  const selectedEmailId = useUIStore((s) => s.selectedEmailId)
  const { data: email, isLoading } = useEmailDetail(selectedEmailId)
  const triggerOne = useTriggerOneEmail()
  const qc = useQueryClient()

  // 邮件加载后（后端已标记已读），使列表缓存失效以更新字体粗细
  useEffect(() => {
    if (email?.id) {
      qc.invalidateQueries({ queryKey: ['emails'] })
    }
  }, [email?.id])

  if (!selectedEmailId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        选择一封邮件以查看详情
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        加载中…
      </div>
    )
  }

  if (!email) return null

  const actionItems: string[] = (() => {
    try { return JSON.parse(email.ai_action_items || '[]') } catch { return [] }
  })()

  const isAnalyzing = triggerOne.isPending || email.ai_status === 'processing'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 邮件头 */}
      <div className="px-4 pt-4 pb-3 border-b border-gray-100 shrink-0">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h2 className="text-base font-semibold text-gray-900 leading-tight flex-1">
            {email.ai_is_important && <span className="text-red-500 mr-1">⚡️</span>}
            {email.subject}
          </h2>
          {/* AI 分析按钮 */}
          {email.ai_status !== 'completed' ? (
            <button
              onClick={() => triggerOne.mutate(email.id)}
              disabled={isAnalyzing}
              className="shrink-0 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-2.5 py-1 transition-colors"
            >
              {isAnalyzing ? '分析中…' : '🤖 AI 分析'}
            </button>
          ) : (
            <button
              onClick={() => triggerOne.mutate(email.id)}
              disabled={isAnalyzing}
              className="shrink-0 text-xs text-gray-400 hover:text-blue-600 transition-colors"
              title="重新分析"
            >
              {isAnalyzing ? '…' : '↺ 重新分析'}
            </button>
          )}
        </div>
        <div className="text-xs text-gray-500 space-y-0.5">
          <div>
            <span className="text-gray-400">发件人：</span>
            <span className="text-gray-700">{email.sender_name || email.sender}</span>
            {email.sender_name && <span className="text-gray-400 ml-1">&lt;{email.sender}&gt;</span>}
          </div>
          <div>
            <span className="text-gray-400">时间：</span>
            <span>{formatDate(email.receive_time)}</span>
          </div>
        </div>
      </div>

      {/* AI 摘要卡片 */}
      {email.ai_status === 'completed' && email.ai_summary && (
        <div className="shrink-0">
          <SummaryCard
            summary={email.ai_summary}
            actionItems={actionItems}
            importance={email.ai_importance}
          />
        </div>
      )}

      {/* AI 处理中提示 */}
      {email.ai_status === 'processing' && (
        <div className="mx-4 mt-3 mb-1 text-xs text-yellow-600 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse inline-block" />
          AI 正在分析中…
        </div>
      )}

      {/* AI 分析失败提示 */}
      {email.ai_status === 'failed' && (
        <div className="mx-4 mt-3 mb-1 text-xs text-red-500 flex items-center gap-1.5">
          <span>⚠️</span>
          <span>AI 分析失败。请在左侧 AI 控制台确认 Ollama 已运行并选择正确模型，然后点击"↺ 重新分析"重试。</span>
        </div>
      )}

      {/* 邮件正文 */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {email.body_html ? (
          <div
            className="prose prose-sm max-w-none text-gray-700"
            dangerouslySetInnerHTML={{ __html: email.body_html }}
          />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
            {email.body_text || '（无正文）'}
          </pre>
        )}
      </div>

      {/* 回复区 */}
      <div className="shrink-0 border-t border-gray-100">
        <GhostReplyEditor key={email.id} email={email} />
      </div>
    </div>
  )
}
