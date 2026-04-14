import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { GhostReplyEditor } from '../ReplyEditor/GhostReplyEditor'
import { useEmailDetail, useSentReplyDetail, useTriggerOneEmail } from '../../hooks/useEmails'
import { useI18n } from '../../i18n'
import { useUIStore } from '../../store/uiStore'
import { SummaryCard } from './SummaryCard'

function useFormatDate() {
  const { language } = useI18n()

  return (dateStr: string): string => {
    const date = new Date(dateStr + 'Z')
    return date.toLocaleString(language, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
}

export function EmailDetail() {
  const selectedItemId = useUIStore((s) => s.selectedItemId)
  const selectedView = useUIStore((s) => s.selectedView)
  const isSentView = selectedView === 'sent'
  const { t } = useI18n()
  const formatDate = useFormatDate()

  const { data: email, isLoading: emailLoading } = useEmailDetail(selectedItemId, !isSentView)
  const { data: sentReply, isLoading: sentLoading } = useSentReplyDetail(selectedItemId, isSentView)
  const triggerOne = useTriggerOneEmail()
  const qc = useQueryClient()

  useEffect(() => {
    if (!isSentView && email?.id) {
      qc.invalidateQueries({ queryKey: ['emails'] })
    }
  }, [email?.id, isSentView, qc])

  if (!selectedItemId) {
    return <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">{t('emailDetailEmpty')}</div>
  }

  if (isSentView) {
    if (sentLoading) {
      return <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">{t('commonLoading')}</div>
    }

    if (!sentReply) return null

    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="border-b border-gray-100 px-4 pt-4 pb-3 shrink-0">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-sky-700">
            {t('sentDetailTitle')}
          </div>
          <h2 className="text-base font-semibold text-gray-900 leading-tight">
            {sentReply.subject || t('sentListNoSubject')}
          </h2>
          <div className="mt-3 space-y-0.5 text-xs text-gray-500">
            <div>
              <span className="text-gray-400">{t('sentDetailRecipient')}</span>
              <span>{sentReply.recipient}</span>
            </div>
            <div>
              <span className="text-gray-400">{t('sentDetailTime')}</span>
              <span>{formatDate(sentReply.sent_at)}</span>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
            {sentReply.body_text || t('commonNoneBody')}
          </pre>
        </div>
      </div>
    )
  }

  if (emailLoading) {
    return <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">{t('commonLoading')}</div>
  }

  if (!email) return null

  const isAnalyzing = triggerOne.isPending || email.ai_status === 'processing'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-4 pt-4 pb-3 border-b border-gray-100 shrink-0">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h2 className="text-base font-semibold text-gray-900 leading-tight flex-1">
            {email.ai_is_important && <span className="text-red-500 mr-1">⚡️</span>}
            {email.subject}
          </h2>
          {email.ai_status !== 'completed' ? (
            <button
              onClick={() => triggerOne.mutate(email.id)}
              disabled={isAnalyzing}
              className="shrink-0 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-2.5 py-1 transition-colors"
            >
              {isAnalyzing ? t('emailDetailAnalyzing') : t('emailDetailAnalyze')}
            </button>
          ) : (
            <button
              onClick={() => triggerOne.mutate(email.id)}
              disabled={isAnalyzing}
              className="shrink-0 text-xs text-gray-400 hover:text-blue-600 transition-colors"
              title={t('emailDetailReanalyzeTitle')}
            >
              {isAnalyzing ? '...' : t('emailDetailReanalyze')}
            </button>
          )}
        </div>
        <div className="text-xs text-gray-500 space-y-0.5">
          <div>
            <span className="text-gray-400">{t('emailDetailSender')}</span>
            <span className="text-gray-700">{email.sender_name || email.sender}</span>
            {email.sender_name && <span className="text-gray-400 ml-1">&lt;{email.sender}&gt;</span>}
          </div>
          <div>
            <span className="text-gray-400">{t('emailDetailTime')}</span>
            <span>{formatDate(email.receive_time)}</span>
          </div>
          <div>
            <span className="text-gray-400">{t('emailDetailFolder')}</span>
            <span>{email.folder}</span>
          </div>
          {email.folders.length > 1 && (
            <div className="flex items-start gap-2">
              <span className="text-gray-400 shrink-0">{t('emailDetailFolders')}</span>
              <div className="flex flex-wrap gap-1.5">
                {email.folders.map((folder) => (
                  <span
                    key={folder}
                    className="inline-flex rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700"
                  >
                    {folder}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {email.ai_status === 'completed' && email.ai_summary && (
        <div className="shrink-0">
          <SummaryCard summary={email.ai_summary} importance={email.ai_importance} />
        </div>
      )}

      {email.ai_status === 'processing' && (
        <div className="mx-4 mt-3 mb-1 text-xs text-yellow-600 flex items-center gap-1.5">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-yellow-400" />
          {t('emailDetailAiProcessing')}
        </div>
      )}

      {email.ai_status === 'failed' && (
        <div className="mx-4 mt-3 mb-1 text-xs text-red-500 flex items-center gap-1.5">
          <span>⚠️</span>
          <span>{t('emailDetailAiFailed')}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {email.body_html ? (
          <div className="prose prose-sm max-w-none text-gray-700" dangerouslySetInnerHTML={{ __html: email.body_html }} />
        ) : (
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
            {email.body_text || t('commonNoneBody')}
          </pre>
        )}

        {email.sent_replies.length > 0 && (
          <div className="mt-5 space-y-3">
            <div className="text-xs font-semibold tracking-wide text-sky-700 uppercase">
              {t('emailDetailSentRepliesTitle')}
            </div>
            {email.sent_replies.map((reply) => (
              <div
                key={reply.id}
                className="rounded-xl border border-sky-100 bg-sky-50/70 px-4 py-3 shadow-sm shadow-sky-100/40"
              >
                <div className="flex items-start justify-between gap-3 text-xs">
                  <div className="min-w-0">
                    {reply.subject && <div className="truncate font-medium text-sky-900">{reply.subject}</div>}
                    <div className="text-sky-700/80">
                      {t('emailDetailSentTo')} {reply.recipient}
                    </div>
                  </div>
                  <div className="shrink-0 text-sky-700/80">{formatDate(reply.sent_at)}</div>
                </div>
                <pre className="mt-3 whitespace-pre-wrap text-sm font-sans leading-relaxed text-slate-700">
                  {reply.body_text}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-gray-100">
        <GhostReplyEditor key={email.id} email={email} />
      </div>
    </div>
  )
}
