import { useState } from 'react'
import { useI18n } from '../../i18n'
import { useCreateAccount, useSyncAccount } from '../../hooks/useEmails'
import type { Account } from '../../types'

interface Props {
  onClose: () => void
}

const PRESETS: Record<
  string,
  { imapHost: string; smtpHost: string; imapPort: number; smtpPort: number }
> = {
  '163.com': { imapHost: 'imap.163.com', smtpHost: 'smtp.163.com', imapPort: 993, smtpPort: 465 },
  '126.com': { imapHost: 'imap.126.com', smtpHost: 'smtp.126.com', imapPort: 993, smtpPort: 465 },
  'yeah.net': { imapHost: 'imap.yeah.net', smtpHost: 'smtp.yeah.net', imapPort: 993, smtpPort: 465 },
  'qq.com': { imapHost: 'imap.qq.com', smtpHost: 'smtp.qq.com', imapPort: 993, smtpPort: 465 },
  'foxmail.com': { imapHost: 'imap.qq.com', smtpHost: 'smtp.qq.com', imapPort: 993, smtpPort: 465 },
  'gmail.com': {
    imapHost: 'imap.gmail.com',
    smtpHost: 'smtp.gmail.com',
    imapPort: 993,
    smtpPort: 465,
  },
  'outlook.com': {
    imapHost: 'outlook.office365.com',
    smtpHost: 'smtp.office365.com',
    imapPort: 993,
    smtpPort: 587,
  },
  'hotmail.com': {
    imapHost: 'outlook.office365.com',
    smtpHost: 'smtp.office365.com',
    imapPort: 993,
    smtpPort: 587,
  },
  'live.com': {
    imapHost: 'outlook.office365.com',
    smtpHost: 'smtp.office365.com',
    imapPort: 993,
    smtpPort: 587,
  },
}

function detectPreset(email: string) {
  const domain = email.split('@')[1]?.toLowerCase()
  return domain ? PRESETS[domain] ?? null : null
}

export function AddAccountModal({ onClose }: Props) {
  const create = useCreateAccount()
  const sync = useSyncAccount()
  const { t } = useI18n()

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
      },
    )
  }

  const inputCls =
    'w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400'
  const labelCls = 'block text-xs font-medium text-gray-600 mb-1'

  if (createdAccount) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl shadow-xl w-96 p-5 space-y-4">
          <div className="text-center">
            <div className="text-2xl mb-2">✓</div>
            <h3 className="font-semibold text-gray-800">{t('addAccountSuccess')}</h3>
            <p className="text-xs text-gray-500 mt-1">{t('addAccountSyncing')}</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-3 space-y-2">
            <div>
              <span className="text-xs text-gray-400">{t('addAccountEmail')}</span>
              <p className="text-sm font-medium text-gray-700">{createdAccount.email}</p>
            </div>
            <div>
              <span className="text-xs text-gray-400">{t('addAccountId')}</span>
              <p className="font-mono text-xs text-gray-600 break-all mt-0.5 select-all">
                {createdAccount.id}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full text-sm bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2"
          >
            {t('commonDone')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-96 p-5 space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold text-gray-800">{t('addAccountTitle')}</h3>

        <div>
          <label className={labelCls}>{t('addAccountEmailLabel')}</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={handleEmailBlur}
            placeholder="your@163.com"
            className={inputCls}
            autoFocus
          />
          <p className="text-xs text-gray-400 mt-0.5">{t('addAccountEmailHelp')}</p>
        </div>

        <div>
          <label className={labelCls}>{t('addAccountDisplayName')}</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder={t('addAccountDisplayNamePlaceholder')}
            className={inputCls}
          />
        </div>

        <div>
          <label className={labelCls}>{t('addAccountPassword')}</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('addAccountPasswordPlaceholder')}
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 text-xs font-medium text-gray-500 uppercase tracking-wide pt-1">
            {t('addAccountImapSettings')}
          </div>
          <div className="col-span-2">
            <label className={labelCls}>{t('addAccountImapServer')}</label>
            <input
              value={imapHost}
              onChange={(e) => setImapHost(e.target.value)}
              placeholder="imap.163.com"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>{t('addAccountPort')}</label>
            <input
              type="number"
              value={imapPort}
              onChange={(e) => setImapPort(Number(e.target.value))}
              className={inputCls}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 text-xs font-medium text-gray-500 uppercase tracking-wide pt-1">
            {t('addAccountSmtpSettings')}
          </div>
          <div className="col-span-2">
            <label className={labelCls}>{t('addAccountSmtpServer')}</label>
            <input
              value={smtpHost}
              onChange={(e) => setSmtpHost(e.target.value)}
              placeholder="smtp.163.com"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>{t('addAccountPort')}</label>
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
            {(create.error as Error).message.includes('409')
              ? t('addAccountExists')
              : (create.error as Error).message}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5"
          >
            {t('commonCancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={create.isPending || !email || !imapHost || !smtpHost || !password}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-1.5"
          >
            {create.isPending ? t('commonAdding') : t('commonAdd')}
          </button>
        </div>
      </div>
    </div>
  )
}
