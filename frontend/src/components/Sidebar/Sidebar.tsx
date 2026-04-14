import { useEffect, useMemo, useState } from 'react'
import { useAccounts, useDeleteAccount, useSyncAccount, useUpdateAccount } from '../../hooks/useEmails'
import { useI18n } from '../../i18n'
import { useUIStore } from '../../store/uiStore'
import type { Account, MailboxView } from '../../types'
import { AIConsole } from './AIConsole'
import { AddAccountModal } from './AddAccountModal'
import { SettingsModal } from './SettingsModal'

const accountViews: MailboxView[] = ['all', 'important', 'unread', 'sent']

function accountLabel(account: Account) {
  return account.display_name || account.email
}

function sidebarViewLabel(view: MailboxView) {
  const labels = {
    all: 'sidebarViewAll',
    important: 'sidebarViewImportant',
    unread: 'sidebarViewUnread',
    sent: 'sidebarViewSent',
  } as const
  return labels[view]
}

export function Sidebar() {
  const { data: accounts = [] } = useAccounts()
  const sync = useSyncAccount()
  const deleteAccount = useDeleteAccount()
  const updateAccount = useUpdateAccount()
  const { t } = useI18n()
  const { selectedAccountId, selectedView, setAccountView } = useUIStore()
  const [showSettings, setShowSettings] = useState(false)
  const [showAddAccount, setShowAddAccount] = useState(false)

  const selectedAccount = useMemo(
    () => accounts.find((account) => account.id === selectedAccountId) ?? null,
    [accounts, selectedAccountId],
  )

  useEffect(() => {
    if (accounts.length === 0) {
      return
    }
    if (!selectedAccountId || !selectedAccount) {
      setAccountView(accounts[0].id, 'all')
    }
  }, [accounts, selectedAccount, selectedAccountId, setAccountView])

  return (
    <aside className="w-64 flex flex-col bg-gray-50 border-r border-gray-200 h-full shrink-0">
      <div className="p-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h1 className="font-semibold text-gray-800 text-sm">{t('appName')}</h1>
          <button
            onClick={() => setShowAddAccount(true)}
            className="inline-flex items-center rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
            title={t('sidebarAddAccountTitle')}
          >
            {t('sidebarAddAccountShort')}
          </button>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-2 space-y-2">
        {accounts.map((acc) => {
          const expanded = selectedAccountId === acc.id
          return (
            <div key={acc.id} className="rounded-xl border border-gray-200 bg-white/80 shadow-sm">
              <div className="flex items-stretch">
                <button
                  onClick={() => setAccountView(acc.id, expanded ? selectedView : 'all')}
                  className={`min-w-0 flex-1 px-3 py-2.5 text-left transition-colors ${
                    expanded ? 'text-blue-700' : 'text-gray-700 hover:bg-gray-100'
                  }`}
                  title={acc.email}
                >
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] ${expanded ? 'text-blue-600' : 'text-gray-400'}`}>
                      {expanded ? '▼' : '▶'}
                    </span>
                    <div className="min-w-0">
                      <div className={`truncate text-sm font-medium ${expanded ? 'text-blue-700' : 'text-gray-800'}`}>
                        {accountLabel(acc)}
                      </div>
                      <div className="truncate text-[11px] text-gray-400">{acc.email}</div>
                    </div>
                  </div>
                </button>

                <div className="flex shrink-0 items-center gap-0.5 pr-2">
                  <button
                    onClick={() => {
                      const pwd = window.prompt(t('sidebarUpdatePasswordPrompt', { email: acc.email }))
                      if (pwd) {
                        updateAccount.mutate(
                          { id: acc.id, data: { password: pwd } },
                          { onSuccess: () => sync.mutate(acc.id) },
                        )
                      }
                    }}
                    disabled={updateAccount.isPending}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-sm text-gray-400 transition-colors hover:bg-gray-100 hover:text-yellow-600"
                    title={t('sidebarUpdatePasswordTitle')}
                  >
                    🔑
                  </button>
                  <button
                    onClick={() => sync.mutate(acc.id)}
                    disabled={sync.isPending}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-sm text-gray-400 transition-colors hover:bg-gray-100 hover:text-blue-600"
                    title={t('sidebarSyncTitle')}
                  >
                    ↻
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm(t('sidebarDeleteConfirm', { email: acc.email }))) {
                        deleteAccount.mutate(acc.id)
                      }
                    }}
                    disabled={deleteAccount.isPending}
                    className="flex h-8 w-8 items-center justify-center rounded-md text-sm text-gray-400 transition-colors hover:bg-gray-100 hover:text-red-500"
                    title={t('sidebarDeleteTitle')}
                  >
                    ✕
                  </button>
                </div>
              </div>

              {expanded && (
                <div className="border-t border-gray-100 px-2 py-2 space-y-1">
                  {accountViews.map((view) => {
                    const active = selectedView === view
                    return (
                      <div key={view} className="flex items-center gap-2">
                        <button
                          onClick={() => setAccountView(acc.id, view)}
                          className={`flex-1 rounded-lg px-3 py-1.5 text-left text-sm transition-colors ${
                            active ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          {t(sidebarViewLabel(view))}
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        {accounts.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-200 bg-white/70 px-3 py-4 text-xs leading-relaxed text-gray-500">
            {t('sidebarNoAccounts')}
          </div>
        )}
      </nav>

      <button
        onClick={() => setShowSettings(true)}
        className="mx-2 mb-1 text-left px-3 py-1.5 rounded text-xs text-gray-500 hover:bg-gray-200 transition-colors"
      >
        {t('sidebarSettings')}
      </button>

      <AIConsole />

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showAddAccount && <AddAccountModal onClose={() => setShowAddAccount(false)} />}
    </aside>
  )
}
