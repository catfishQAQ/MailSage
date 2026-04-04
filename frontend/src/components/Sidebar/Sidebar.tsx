import { useState } from 'react'
import { useAccounts, useSyncAccount, useDeleteAccount, useUpdateAccount } from '../../hooks/useEmails'
import { useUIStore } from '../../store/uiStore'
import { AIConsole } from './AIConsole'
import { SettingsModal } from './SettingsModal'
import { AddAccountModal } from './AddAccountModal'

export function Sidebar() {
  const { data: accounts = [] } = useAccounts()
  const sync = useSyncAccount()
  const deleteAccount = useDeleteAccount()
  const updateAccount = useUpdateAccount()
  const { selectedAccountId, filterImportant, setSelectedAccount, setFilterImportant } = useUIStore()
  const [showSettings, setShowSettings] = useState(false)
  const [showAddAccount, setShowAddAccount] = useState(false)

  return (
    <aside className="w-52 flex flex-col bg-gray-50 border-r border-gray-200 h-full shrink-0">
      <div className="p-3 border-b border-gray-200">
        <h1 className="font-semibold text-gray-800 text-sm">MailSage</h1>
      </div>

      {/* 导航 */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
        <button
          onClick={() => { setSelectedAccount(null); setFilterImportant(false) }}
          className={`w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
            !selectedAccountId && !filterImportant
              ? 'bg-blue-100 text-blue-700 font-medium'
              : 'text-gray-700 hover:bg-gray-200'
          }`}
        >
          📥 所有收件箱
        </button>
        <button
          onClick={() => setFilterImportant(true)}
          className={`w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
            filterImportant ? 'bg-red-50 text-red-700 font-medium' : 'text-gray-700 hover:bg-gray-200'
          }`}
        >
          ⚡️ 重要邮件
        </button>

        {/* 各邮箱账号 */}
        <div className="pt-2">
          <div className="px-3 flex items-center justify-between mb-1">
            <span className="text-xs text-gray-400 uppercase tracking-wide">账号</span>
            <button
              onClick={() => setShowAddAccount(true)}
              className="text-xs text-gray-400 hover:text-blue-600 leading-none"
              title="添加账号"
            >
              +
            </button>
          </div>
          {accounts.map((acc) => (
            <div key={acc.id} className="group flex items-center">
              <button
                onClick={() => { setSelectedAccount(acc.id); setFilterImportant(false) }}
                className={`flex-1 text-left px-3 py-1.5 rounded-l text-xs truncate transition-colors ${
                  selectedAccountId === acc.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-200'
                }`}
                title={acc.email}
              >
                {acc.display_name || acc.email}
              </button>
              <button
                onClick={() => {
                  const pwd = window.prompt(`更新 ${acc.email} 的授权码：`)
                  if (pwd) {
                    updateAccount.mutate(
                      { id: acc.id, data: { password: pwd } },
                      { onSuccess: () => sync.mutate(acc.id) }
                    )
                  }
                }}
                disabled={updateAccount.isPending}
                className="hidden group-hover:flex px-1.5 py-1.5 text-xs text-gray-400 hover:text-yellow-600 hover:bg-gray-200"
                title="更新授权码"
              >
                🔑
              </button>
              <button
                onClick={() => sync.mutate(acc.id)}
                disabled={sync.isPending}
                className="hidden group-hover:flex px-1.5 py-1.5 text-xs text-gray-400 hover:text-blue-600 hover:bg-gray-200"
                title="同步"
              >
                ↻
              </button>
              <button
                onClick={() => {
                  if (window.confirm(`删除账号 ${acc.email}？相关邮件也会一并删除。`)) {
                    deleteAccount.mutate(acc.id)
                  }
                }}
                disabled={deleteAccount.isPending}
                className="hidden group-hover:flex px-1.5 py-1.5 text-xs text-gray-400 hover:text-red-500 hover:bg-gray-200 rounded-r"
                title="删除账号"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </nav>

      {/* 设置按钮 */}
      <button
        onClick={() => setShowSettings(true)}
        className="mx-2 mb-1 text-left px-3 py-1.5 rounded text-xs text-gray-500 hover:bg-gray-200 transition-colors"
      >
        ⚙️ 设置
      </button>

      {/* AI 控制台固定在底部 */}
      <AIConsole />

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showAddAccount && <AddAccountModal onClose={() => setShowAddAccount(false)} />}
    </aside>
  )
}
