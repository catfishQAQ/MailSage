import { useState, useRef, useCallback, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { EmailDetail } from '../../types'

type GhostState = 'ghost' | 'overridden' | 'expanded'

interface Props {
  email: EmailDetail
}

export function GhostReplyEditor({ email }: Props) {
  const [state, setState] = useState<GhostState>(
    email.ai_ghost_reply ? 'ghost' : 'overridden'
  )
  const [userInput, setUserInput] = useState('')
  const [expandedText, setExpandedText] = useState('')
  const [sendSuccess, setSendSuccess] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const qc = useQueryClient()

  const ghostText = email.ai_ghost_reply || ''

  // AI 分析完成后自动切换到 ghost 状态（处理 AI 处理中打开邮件的情况）
  useEffect(() => {
    if (email.ai_ghost_reply && state === 'overridden' && !userInput) {
      setState('ghost')
    }
  }, [email.ai_ghost_reply])

  // AI 扩写
  const expand = useMutation({
    mutationFn: (draft: string) => api.ai.expandReply(email.id, draft),
    onSuccess: (data) => {
      setExpandedText(data.expanded)
      setState('expanded')
    },
  })

  // 发信
  const send = useMutation({
    mutationFn: async (body: string) => {
      // 目前通过 SMTP 服务发信（需传入 account_id、收件人等信息）
      const res = await fetch('/api/emails/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: email.account_id,
          to: email.sender,
          subject: email.subject.startsWith('Re:') ? email.subject : `Re: ${email.subject}`,
          body,
          reply_to_message_id: email.id,
        }),
      })
      if (!res.ok) throw new Error('发送失败')
      return res.json()
    },
    onSuccess: () => {
      setSendSuccess(true)
      setState('ghost')
      setUserInput('')
      setExpandedText('')
    },
  })

  const handleUserType = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setUserInput(e.target.value)
    if (state === 'ghost') setState('overridden')
  }, [state])

  const handleExpand = () => {
    const draft = state === 'ghost' ? ghostText : userInput
    if (!draft.trim()) return
    expand.mutate(draft)
  }

  const handleSend = () => {
    const body = state === 'expanded' ? expandedText : (state === 'ghost' ? ghostText : userInput)
    if (!body.trim()) return
    send.mutate(body)
  }

  return (
    <div className="p-3 space-y-2">
      <div className="text-xs text-gray-400 font-medium">回复</div>

      {state === 'expanded' ? (
        /* 扩写后展示完整邮件 */
        <textarea
          value={expandedText}
          onChange={(e) => setExpandedText(e.target.value)}
          rows={8}
          className="w-full text-sm text-gray-800 border border-gray-200 rounded p-2.5 resize-none focus:outline-none focus:border-blue-400"
        />
      ) : (
        /* Ghost text / 用户输入 */
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
          placeholder={state === 'ghost' ? ghostText : '输入回复草稿…'}
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
            {expand.isPending ? '润色中…' : '✨ AI 润色 / 扩写'}
          </button>
        )}
        {state === 'expanded' && (
          <button
            onClick={() => setState('overridden')}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            重新编辑
          </button>
        )}
        <button
          onClick={handleSend}
          disabled={send.isPending}
          className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-3 py-1.5 transition-colors ml-auto"
        >
          {send.isPending ? '发送中…' : '发送'}
        </button>
      </div>

      {sendSuccess && (
        <div className="text-xs text-green-600">✓ 已发送</div>
      )}
      {expand.error && (
        <div className="text-xs text-red-500">扩写失败，请检查 Ollama 是否运行</div>
      )}
      {send.error && (
        <div className="text-xs text-red-500">发送失败，请检查账号配置</div>
      )}
    </div>
  )
}
