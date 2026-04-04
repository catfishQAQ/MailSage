import { useEmailList } from '../../hooks/useEmails'
import { useUIStore } from '../../store/uiStore'
import { EmailItem } from './EmailItem'

export function EmailList() {
  const { selectedAccountId, selectedEmailId, filterImportant, setSelectedEmail } = useUIStore()

  const { data, isLoading, error } = useEmailList({
    account_id: selectedAccountId ?? undefined,
    is_important: filterImportant ? true : undefined,
  })

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        加载中…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-400 text-sm">
        加载失败
      </div>
    )
  }

  const emails = data?.items ?? []

  if (emails.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        {filterImportant ? '没有重要邮件' : '收件箱为空'}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-200 text-xs text-gray-500">
        共 {data?.total ?? 0} 封{filterImportant ? ' · 仅重要' : ''}
      </div>
      <div className="flex-1 overflow-y-auto">
        {emails.map((item) => (
          <EmailItem
            key={item.id}
            item={item}
            isSelected={selectedEmailId === item.id}
            onClick={() => setSelectedEmail(item.id)}
          />
        ))}
      </div>
    </div>
  )
}
