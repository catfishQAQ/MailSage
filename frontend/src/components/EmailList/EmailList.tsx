import { useEmailList } from '../../hooks/useEmails'
import { useI18n } from '../../i18n'
import { useUIStore } from '../../store/uiStore'
import { EmailItem } from './EmailItem'

export function EmailList() {
  const { selectedAccountId, selectedEmailId, filterImportant, setSelectedEmail } = useUIStore()
  const { t } = useI18n()

  const { data, isLoading, error } = useEmailList({
    account_id: selectedAccountId ?? undefined,
    is_important: filterImportant ? true : undefined,
  })

  if (isLoading) {
    return <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">{t('commonLoading')}</div>
  }

  if (error) {
    return <div className="flex-1 flex items-center justify-center text-red-400 text-sm">{t('commonLoadFailed')}</div>
  }

  const emails = data?.items ?? []

  if (emails.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        {filterImportant ? t('emailListEmptyImportant') : t('emailListEmpty')}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-200 text-xs text-gray-500">
        {t('emailListTotal', { count: data?.total ?? 0 })}
        {filterImportant ? t('emailListTotalImportantSuffix') : ''}
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
