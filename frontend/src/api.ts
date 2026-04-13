import type {
  Account,
  EmailListResponse,
  EmailDetail,
  SentReply,
  Persona,
  OllamaStatus,
  AIStatus,
} from './types'

const BASE = '/api'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${url} failed (${res.status}): ${text}`)
  }
  if (res.status === 204) {
    return undefined as T
  }
  return res.json()
}

// ── Accounts ──────────────────────────────────────────────
export const api = {
  accounts: {
    list: () => request<Account[]>('/accounts/'),
    create: (data: {
      email: string
      display_name?: string
      imap_host: string
      imap_port?: number
      imap_use_ssl?: boolean
      smtp_host: string
      smtp_port?: number
      smtp_use_ssl?: boolean
      password: string
    }) => request<Account>('/accounts/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: { password?: string; display_name?: string }) =>
      request<Account>(`/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/accounts/${id}`, { method: 'DELETE' }),
    sync: (id: string) => request<{ message: string }>(`/accounts/${id}/sync`, { method: 'POST' }),
  },

  emails: {
    list: (params: {
      account_id?: string
      ai_status?: AIStatus
      is_important?: boolean
      page?: number
      page_size?: number
    }) => {
      const q = new URLSearchParams()
      if (params.account_id) q.set('account_id', params.account_id)
      if (params.ai_status) q.set('ai_status', params.ai_status)
      if (params.is_important != null) q.set('is_important', String(params.is_important))
      if (params.page) q.set('page', String(params.page))
      if (params.page_size) q.set('page_size', String(params.page_size))
      return request<EmailListResponse>(`/emails/?${q}`)
    },
    get: (id: string) => request<EmailDetail>(`/emails/${id}`),
    send: (data: {
      account_id: string
      to: string
      subject: string
      body: string
      reply_to_message_id?: string | null
    }) =>
      fetch(BASE + '/emails/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }).then(async (res) => {
        if (!res.ok) {
          const payload = await res.json().catch(() => ({} as { detail?: string }))
          throw new Error(payload.detail || 'send_failed')
        }
        return res.json() as Promise<{ ok: true; sent_reply: SentReply }>
      }),
    pendingCount: () => request<{ pending: number }>('/emails/pending/count'),
  },

  ai: {
    trigger: () => request<{ queued_count: number; message: string }>('/ai/trigger', { method: 'POST' }),
    triggerOne: (id: string) => request<{ message: string }>(`/ai/trigger/${id}`, { method: 'POST' }),
    status: () => request<OllamaStatus>('/ai/status'),
    expandReply: (email_id: string, draft: string) =>
      request<{ expanded: string }>('/ai/expand_reply', {
        method: 'POST',
        body: JSON.stringify({ email_id, draft }),
      }),
  },

  settings: {
    getPersona: () => request<Persona>('/settings/persona'),
    updatePersona: (data: Partial<Persona>) =>
      request<Persona>('/settings/persona', { method: 'PUT', body: JSON.stringify(data) }),
  },
}
