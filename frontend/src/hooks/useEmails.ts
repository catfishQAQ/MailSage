import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import type { AIStatus, MailboxView } from '../types'

export function useEmailList(params: {
  account_id?: string
  ai_status?: AIStatus
  view?: Exclude<MailboxView, 'sent'>
  page?: number
}) {
  return useQuery({
    queryKey: ['emails', params],
    queryFn: () => api.emails.list({ ...params, page_size: 50 }),
    enabled: !!params.account_id,
    refetchInterval: 60_000,
  })
}

export function useSentReplyList(params: { account_id?: string; page?: number }) {
  return useQuery({
    queryKey: ['sent-replies', params],
    queryFn: () => api.emails.listSent({ ...params, page_size: 50 }),
    enabled: !!params.account_id,
    refetchInterval: 60_000,
  })
}

export function useEmailDetail(id: string | null, enabled = true) {
  return useQuery({
    queryKey: ['email', id],
    queryFn: () => api.emails.get(id!),
    enabled: enabled && id != null,
  })
}

export function useSentReplyDetail(id: string | null, enabled = true) {
  return useQuery({
    queryKey: ['sent-reply', id],
    queryFn: () => api.emails.getSent(id!),
    enabled: enabled && id != null,
  })
}

export function usePendingCount(accountId?: string | null) {
  return useQuery({
    queryKey: ['pending-count', accountId ?? 'all'],
    queryFn: () => api.emails.pendingCount(accountId ?? undefined),
    refetchInterval: 10_000,
  })
}

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: () => api.accounts.list(),
  })
}

export function useSyncAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.accounts.sync(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email'] })
      qc.invalidateQueries({ queryKey: ['sent-replies'] })
      qc.invalidateQueries({ queryKey: ['sent-reply'] })
      qc.invalidateQueries({ queryKey: ['pending-count'] })
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 3000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 7000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 12000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['sent-replies'] }), 3000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['sent-replies'] }), 7000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['sent-replies'] }), 12000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['email'] }), 3000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['email'] }), 7000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['email'] }), 12000)
    },
  })
}

export function useTriggerAI() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.ai.trigger(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pending-count'] })
    },
  })
}

export function useTriggerOneEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.ai.triggerOne(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['email', id] })
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['pending-count'] })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => api.emails.markAllRead(accountId),
    onSuccess: (_, accountId) => {
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['email'] })
      qc.invalidateQueries({ queryKey: ['pending-count', accountId] })
    },
  })
}

export function useOllamaStatus() {
  return useQuery({
    queryKey: ['ollama-status'],
    queryFn: () => api.ai.status(),
    refetchInterval: 5_000,
  })
}

export function usePersona() {
  return useQuery({
    queryKey: ['persona'],
    queryFn: () => api.settings.getPersona(),
  })
}

export function useCreateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof api.accounts.create>[0]) => api.accounts.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
    },
  })
}

export function useDeleteAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.accounts.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['emails'] })
      qc.invalidateQueries({ queryKey: ['sent-replies'] })
    },
  })
}

export function useUpdateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { password?: string; display_name?: string; prompt_context?: string | null }
    }) => api.accounts.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
    },
  })
}
