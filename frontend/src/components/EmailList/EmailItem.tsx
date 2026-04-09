import { useI18n } from '../../i18n'
import { mergeAIUpdate, useUIStore } from '../../store/uiStore'
import type { EmailListItem } from '../../types'

function importanceCls(score: number): string {
  if (score >= 5) return 'bg-red-100 text-red-600'
  if (score >= 4) return 'bg-orange-100 text-orange-600'
  if (score >= 3) return 'bg-yellow-100 text-yellow-700'
  if (score >= 2) return 'bg-blue-50 text-blue-500'
  return 'bg-gray-100 text-gray-400'
}

interface Props {
  item: EmailListItem
  isSelected: boolean
  onClick: () => void
}

export function EmailItem({ item, isSelected, onClick }: Props) {
  const aiUpdates = useUIStore((s) => s.aiUpdates)
  const { language, t } = useI18n()
  const merged = mergeAIUpdate(item, aiUpdates)

  function formatTime(dateStr: string): string {
    const date = new Date(dateStr + 'Z')
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffDays === 0) {
      return date.toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' })
    }
    if (diffDays < 7) {
      return date.toLocaleDateString(language, { weekday: 'short' })
    }
    return date.toLocaleDateString(language, { month: 'numeric', day: 'numeric' })
  }

  return (
    <div
      onClick={onClick}
      className={`px-3 py-2.5 border-b border-gray-100 cursor-pointer transition-colors ${
        isSelected ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'
      } ${!merged.is_read ? 'bg-white' : 'bg-gray-50/50'}`}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        {merged.ai_is_important && (
          <span className="text-red-500 text-xs shrink-0" title={t('emailListImportantTitle')}>
            ⚡️
          </span>
        )}
        {merged.ai_status === 'pending' && (
          <span className="w-1.5 h-1.5 rounded-full bg-gray-300 shrink-0" title={t('emailListPendingTitle')} />
        )}
        {merged.ai_status === 'processing' && (
          <span
            className="w-1.5 h-1.5 rounded-full bg-yellow-400 shrink-0 animate-pulse"
            title={t('emailListProcessingTitle')}
          />
        )}
        <span
          className={`text-xs truncate flex-1 ${!merged.is_read ? 'font-semibold text-gray-900' : 'text-gray-600'}`}
        >
          {merged.sender_name || merged.sender}
        </span>
        <span className="text-xs text-gray-400 shrink-0">{formatTime(merged.receive_time)}</span>
      </div>

      <div className={`text-xs truncate ${!merged.is_read ? 'font-medium text-gray-800' : 'text-gray-600'}`}>
        {merged.subject}
      </div>

      {merged.ai_summary && (
        <div className="flex items-start gap-1.5 mt-1">
          {merged.ai_importance !== null && (
            <span
              className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${importanceCls(merged.ai_importance)}`}
            >
              {merged.ai_importance}/5
            </span>
          )}
          <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{merged.ai_summary}</p>
        </div>
      )}
    </div>
  )
}
