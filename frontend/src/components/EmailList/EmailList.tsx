import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../../i18n'
import { useEmailList, useMarkAllRead, useSentReplyList } from '../../hooks/useEmails'
import { useUIStore } from '../../store/uiStore'
import type { MailboxView, SentReply } from '../../types'
import { EmailItem } from './EmailItem'

function viewTitleKey(view: MailboxView) {
  const titles = {
    all: 'sidebarViewAll',
    important: 'sidebarViewImportant',
    unread: 'sidebarViewUnread',
    sent: 'sidebarViewSent',
  } as const satisfies Record<MailboxView, string>
  return titles[view]
}

function SentReplyItem({
  item,
  isSelected,
  onClick,
}: {
  item: SentReply
  isSelected: boolean
  onClick: () => void
}) {
  const { language, t } = useI18n()

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
      className={`cursor-pointer border-b border-gray-100 px-3 py-2.5 transition-colors ${
        isSelected ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'
      }`}
    >
      <div className="mb-0.5 flex items-center gap-1.5">
        <span className="flex-1 truncate text-xs font-semibold text-gray-800">{item.recipient}</span>
        <span className="shrink-0 text-xs text-gray-400">{formatTime(item.sent_at)}</span>
      </div>
      <div className="truncate text-xs font-medium text-gray-700">{item.subject || t('sentListNoSubject')}</div>
      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-gray-500">{item.body_text}</p>
    </div>
  )
}

export function EmailList() {
  const { selectedAccountId, selectedItemId, selectedView, setSelectedItem } = useUIStore()
  const { t } = useI18n()
  const markAllRead = useMarkAllRead()
  const [showUnreadConfirm, setShowUnreadConfirm] = useState(false)
  const unreadConfirmRef = useRef<HTMLDivElement | null>(null)

  const emailView = selectedView === 'sent' ? undefined : selectedView
  const emailList = useEmailList({
    account_id: selectedAccountId ?? undefined,
    view: emailView as Exclude<MailboxView, 'sent'> | undefined,
  })
  const sentList = useSentReplyList({
    account_id: selectedAccountId ?? undefined,
  })

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!unreadConfirmRef.current?.contains(event.target as Node)) {
        setShowUnreadConfirm(false)
      }
    }

    if (showUnreadConfirm) {
      document.addEventListener('mousedown', handlePointerDown)
      return () => document.removeEventListener('mousedown', handlePointerDown)
    }
  }, [showUnreadConfirm])

  if (!selectedAccountId) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-gray-400">
        {t('emailListSelectAccount')}
      </div>
    )
  }

  const isSentView = selectedView === 'sent'
  const isLoading = isSentView ? sentList.isLoading : emailList.isLoading
  const error = isSentView ? sentList.error : emailList.error

  if (isLoading) {
    return <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">{t('commonLoading')}</div>
  }

  if (error) {
    return <div className="flex-1 flex items-center justify-center text-red-400 text-sm">{t('commonLoadFailed')}</div>
  }

  const total = isSentView ? sentList.data?.total ?? 0 : emailList.data?.total ?? 0
  const emptyText =
    selectedView === 'important'
      ? t('emailListEmptyImportant')
      : selectedView === 'unread'
        ? t('emailListEmptyUnread')
        : selectedView === 'sent'
          ? t('emailListEmptySent')
          : t('emailListEmpty')

  const titleKey = viewTitleKey(selectedView)
  const itemsEmpty = isSentView ? (sentList.data?.items ?? []).length === 0 : (emailList.data?.items ?? []).length === 0

  function renderHeader() {
    return (
      <div className="border-b border-gray-200 px-3 py-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-medium text-gray-700">{t(titleKey)}</div>
            <div className="mt-0.5 text-xs text-gray-500">{t('emailListTotal', { count: total })}</div>
          </div>

          {selectedView === 'unread' && (
            <div ref={unreadConfirmRef} className="relative shrink-0">
              <button
                onClick={() => setShowUnreadConfirm((value) => !value)}
                className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] font-medium text-amber-700 transition-colors hover:bg-amber-100"
                title={t('sidebarClearUnreadTitle')}
              >
                {markAllRead.isPending ? t('sidebarClearingUnread') : t('sidebarClearUnread')}
              </button>

              {showUnreadConfirm && (
                <div className="absolute right-0 top-[calc(100%+8px)] z-10 w-48 rounded-lg border border-gray-200 bg-white p-2 shadow-xl">
                  <div className="px-2 pb-2 text-[11px] leading-relaxed text-gray-500">
                    {t('emailListUnreadConfirmText')}
                  </div>
                  <div className="space-y-1">
                    <button
                      onClick={() => {
                        markAllRead.mutate(selectedAccountId!, {
                          onSuccess: () => {
                            setSelectedItem(null)
                            setShowUnreadConfirm(false)
                          },
                        })
                      }}
                      disabled={markAllRead.isPending}
                      className="w-full rounded-md bg-amber-500 px-3 py-1.5 text-left text-xs font-medium text-white transition-colors hover:bg-amber-600 disabled:opacity-50"
                    >
                      {t('emailListUnreadConfirmAction')}
                    </button>
                    <button
                      onClick={() => setShowUnreadConfirm(false)}
                      className="w-full rounded-md px-3 py-1.5 text-left text-xs text-gray-500 transition-colors hover:bg-gray-100"
                    >
                      {t('commonCancel')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  if (itemsEmpty) {
    return (
      <div className="flex h-full flex-col">
        {renderHeader()}
        <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-gray-400">
          {emptyText}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {renderHeader()}
      <div className="flex-1 overflow-y-auto">
        {isSentView
          ? (sentList.data?.items ?? []).map((item) => (
              <SentReplyItem
                key={item.id}
                item={item}
                isSelected={selectedItemId === item.id}
                onClick={() => setSelectedItem(item.id)}
              />
            ))
          : (emailList.data?.items ?? []).map((item) => (
              <EmailItem
                key={item.id}
                item={item}
                isSelected={selectedItemId === item.id}
                onClick={() => setSelectedItem(item.id)}
              />
            ))}
      </div>
    </div>
  )
}
