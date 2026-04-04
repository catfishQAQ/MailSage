import { useState } from 'react'
import { useCreateAccount } from '../../hooks/useEmails'
import { useSyncAccount } from '../../hooks/useEmails'
import type { Account } from '../../types'

interface Props {
  onClose: () => void
}

// 根据邮箱域名自动填充 IMAP/SMTP 配置
const PRESETS: Record<string, { imapHost: string; smtpHost: string; imapPort: number; smtpPort: number }> = {
  '163.com':     { imapHost: 'imap.163.com',              smtpHost: 'smtp.163.com',              imapPort: 993, smtpPort: 465 },
  '126.com':     { imapHost: 'imap.126.com',              smtpHost: 'smtp.126.com',              imapPort: 993, smtpPort: 465 },
  'yeah.net':    { imapHost: 'imap.yeah.net',             smtpHost: 'smtp.yeah.net',             imapPort: 993, smtpPort: 465 },
  'qq.com':      { imapHost: 'imap.qq.com',               smtpHost: 'smtp.qq.com',               imapPort: 993, smtpPort: 465 },
  'foxmail.com': { imapHost: 'imap.qq.com',               smtpHost: 'smtp.qq.com',               imapPort: 993, smtpPort: 465 },
  'gmail.com':   { imapHost: 'imap.gmail.com',            smtpHost: 'smtp.gmail.com',            imapPort: 993, smtpPort: 465 },
  'outlook.com': { imapHost: 'outlook.office365.com',     smtpHost: 'smtp.office365.com',        imapPort: 993, smtpPort: 587 },
  'hotmail.com': { imapHost: 'outlook.office365.com',     smtpHost: 'smtp.office365.com',        imapPort: 993, smtpPort: 587 },
  'live.com':    { imapHost: 'outlook.office365.com',     smtpHost: 'smtp.office365.com',        imapPort: 993, smtpPort: 587 },
}

function detectPreset(email: string) {
  const domain = email.split('@')[1]?.toLowerCase()
  return domain ? PRESETS[domain] ?? null : null
}

export function AddAccountModal({ onClose }: Props) {
  const create = useCreateAccount()
  const sync = useSyncAccount()

  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [imapHost, setImapHost] = useState('')
  const [imapPort, setImapPort] = useState(993)
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState(465)
  const [password, setPassword] = useState('')
  const [createdAccount, setCreatedAccount] = useState<Account | null>(null)

  function handleEmailBlur() {
    const preset = detectPreset(email)
    if (preset && !imapHost) {
      setImapHost(preset.imapHost)
      setSmtpHost(preset.smtpHost)
      setImapPort(preset.imapPort)
      setSmtpPort(preset.smtpPort)
    }
  }

  function handleSubmit() {
    if (!email || !imapHost || !smtpHost || !password) return
    create.mutate(
      {
        email,
        display_name: displayName || undefined,
        imap_host: imapHost,
        imap_port: imapPort,
        imap_use_ssl: true,
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_use_ssl: true,
        password,
      },
      {
        onSuccess: (acc) => {
          setCreatedAccount(acc)
          sync.mutate(acc.id)
        },
      }
    )
  }

  const inputCls = 'w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400'
  const labelCls = 'block text-xs font-medium text-gray-600 mb-1'

  // 成功状态
  if (createdAccount) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl shadow-xl w-96 p-5 space-y-4">
          <div className="text-center">
            <div className="text-2xl mb-2">✅</div>
            <h3 className="font-semibold text-gray-800">账号添加成功</h3>
            <p className="text-xs text-gray-500 mt-1">正在后台触发首次同步（约拉取最近 200 封）</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-3 space-y-2">
            <div>
              <span className="text-xs text-gray-400">邮箱</span>
              <p className="text-sm font-medium text-gray-700">{createdAccount.email}</p>
            </div>
            <div>
              <span className="text-xs text-gray-400">账号 ID（备用）</span>
              <p className="font-mono text-xs text-gray-600 break-all mt-0.5 select-all">{createdAccount.id}</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full text-sm bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2"
          >
            完成
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-96 p-5 space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold text-gray-800">添加邮箱账号</h3>

        <div>
          <label className={labelCls}>邮箱地址 *</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={handleEmailBlur}
            placeholder="your@163.com"
            className={inputCls}
            autoFocus
          />
          <p className="text-xs text-gray-400 mt-0.5">输入邮箱后失焦，自动填充 IMAP/SMTP 配置</p>
        </div>

        <div>
          <label className={labelCls}>显示名称（可选）</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="例：我的工作邮箱"
            className={inputCls}
          />
        </div>

        <div>
          <label className={labelCls}>授权码 / 应用专用密码 *</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="非登录密码，需在邮箱设置中生成"
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 text-xs font-medium text-gray-500 uppercase tracking-wide pt-1">IMAP 设置</div>
          <div className="col-span-2">
            <label className={labelCls}>IMAP 服务器 *</label>
            <input value={imapHost} onChange={(e) => setImapHost(e.target.value)} placeholder="imap.163.com" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>端口</label>
            <input
              type="number"
              value={imapPort}
              onChange={(e) => setImapPort(Number(e.target.value))}
              className={inputCls}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 text-xs font-medium text-gray-500 uppercase tracking-wide pt-1">SMTP 设置</div>
          <div className="col-span-2">
            <label className={labelCls}>SMTP 服务器 *</label>
            <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.163.com" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>端口</label>
            <input
              type="number"
              value={smtpPort}
              onChange={(e) => setSmtpPort(Number(e.target.value))}
              className={inputCls}
            />
          </div>
        </div>

        {create.error && (
          <p className="text-xs text-red-500">
            {(create.error as Error).message.includes('409') ? '该邮箱已添加' : (create.error as Error).message}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={create.isPending || !email || !imapHost || !smtpHost || !password}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-1.5"
          >
            {create.isPending ? '添加中…' : '添加'}
          </button>
        </div>
      </div>
    </div>
  )
}
