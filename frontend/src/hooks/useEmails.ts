import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import type { AIStatus } from '../types'

export function useEmailList(params: {
  account_id?: string
  ai_status?: AIStatus
  is_important?: boolean
  page?: number
}) {
  return useQuery({
    queryKey: ['emails', params],
    queryFn: () => api.emails.list({ ...params, page_size: 50 }),
    refetchInterval: 60_000,
  })
}

export function useEmailDetail(id: string | null) {
  return useQuery({
    queryKey: ['email', id],
    queryFn: () => api.emails.get(id!),
    enabled: id != null,
  })
}

export function usePendingCount() {
  return useQuery({
    queryKey: ['pending-count'],
    queryFn: () => api.emails.pendingCount(),
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
      qc.invalidateQueries({ queryKey: ['pending-count'] })
      // IMAP 同步是后台任务（202），延迟多次重拉以覆盖同步窗口期
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 3000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 7000)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emails'] }), 12000)
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
    },
  })
}

export function useUpdateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { password?: string; display_name?: string } }) =>
      api.accounts.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
    },
  })
}
