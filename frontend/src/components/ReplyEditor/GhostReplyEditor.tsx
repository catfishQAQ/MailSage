import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { useI18n } from '../../i18n'
import type { EmailDetail } from '../../types'

type GhostState = 'ghost' | 'overridden' | 'expanded'

interface Props {
  email: EmailDetail
}

export function GhostReplyEditor({ email }: Props) {
  const qc = useQueryClient()
  const [state, setState] = useState<GhostState>(email.ai_ghost_reply ? 'ghost' : 'overridden')
  const [userInput, setUserInput] = useState('')
  const [expandedText, setExpandedText] = useState('')
  const [sendSuccess, setSendSuccess] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { t } = useI18n()

  const ghostText = email.ai_ghost_reply || ''

  useEffect(() => {
    if (email.ai_ghost_reply && state === 'overridden' && !userInput) {
      setState('ghost')
    }
  }, [email.ai_ghost_reply, state, userInput])

  const expand = useMutation({
    mutationFn: (draft: string) => api.ai.expandReply(email.id, draft),
    onSuccess: (data) => {
      setExpandedText(data.expanded)
      setState('expanded')
    },
  })

  const send = useMutation({
    mutationFn: (body: string) =>
      api.emails.send({
          account_id: email.account_id,
          to: email.sender,
          subject: email.subject.startsWith('Re:') ? email.subject : `Re: ${email.subject}`,
          body,
          reply_to_message_id: email.message_id || email.id,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['email', email.id] })
      qc.invalidateQueries({ queryKey: ['sent-replies'] })
      qc.invalidateQueries({ queryKey: ['sent-reply'] })
      setSendSuccess(true)
      setState('ghost')
      setUserInput('')
      setExpandedText('')
    },
  })

  const handleUserType = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setUserInput(e.target.value)
      if (state === 'ghost') setState('overridden')
    },
    [state],
  )

  const handleExpand = () => {
    const draft = state === 'ghost' ? ghostText : userInput
    if (!draft.trim()) return
    expand.mutate(draft)
  }

  const handleSend = () => {
    const body = state === 'expanded' ? expandedText : state === 'ghost' ? ghostText : userInput
    if (!body.trim()) return
    send.mutate(body)
  }

  return (
    <div className="p-3 space-y-2">
      <div className="text-xs text-gray-400 font-medium">{t('replyTitle')}</div>

      {state === 'expanded' ? (
        <textarea
          value={expandedText}
          onChange={(e) => setExpandedText(e.target.value)}
          rows={8}
          className="w-full text-sm text-gray-800 border border-gray-200 rounded p-2.5 resize-none focus:outline-none focus:border-blue-400"
        />
      ) : (
        <textarea
          ref={textareaRef}
          value={state === 'ghost' ? '' : userInput}
          onChange={handleUserType}
          onClick={() => {
            if (state === 'ghost') {
              setState('overridden')
              textareaRef.current?.focus()
            }
          }}
          placeholder={state === 'ghost' ? ghostText : t('replyPlaceholder')}
          rows={4}
          className={`w-full text-sm border border-gray-200 rounded p-2.5 resize-none focus:outline-none focus:border-blue-400 ${
            state === 'ghost' ? 'ghost-text text-gray-400' : 'text-gray-800'
          }`}
        />
      )}

      <div className="flex items-center gap-2">
        {state !== 'expanded' && (
          <button
            onClick={handleExpand}
            disabled={expand.isPending || (state === 'overridden' && !userInput.trim())}
            className="text-xs bg-purple-600 hover:bg-purple-700 disabled:bg-gray-200 disabled:text-gray-400 text-white rounded px-3 py-1.5 transition-colors"
          >
            {expand.isPending ? t('replyPolishing') : t('replyPolish')}
          </button>
        )}
        {state === 'expanded' && (
          <button
            onClick={() => setState('overridden')}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            {t('replyEditAgain')}
          </button>
        )}
        <button
          onClick={handleSend}
          disabled={send.isPending}
          className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-3 py-1.5 transition-colors ml-auto"
        >
          {send.isPending ? t('replySending') : t('replySend')}
        </button>
      </div>

      {sendSuccess && <div className="text-xs text-green-600">{t('replySent')}</div>}
      {expand.error && <div className="text-xs text-red-500">{t('replyExpandFailed')}</div>}
      {send.error && (
        <div className="text-xs text-red-500">
          {t('replySendFailed')}: {(send.error as Error).message}
        </div>
      )}
    </div>
  )
}
