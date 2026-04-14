import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { useAccounts, useOllamaStatus, usePersona } from '../../hooks/useEmails'
import { type AppLanguage, getPromptTemplates, getScheduleOptions, useI18n } from '../../i18n'
import { useUIStore } from '../../store/uiStore'

interface Props {
  onClose: () => void
}

const inputCls =
  'w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400'
const labelCls = 'block text-xs font-medium text-gray-600 mb-1'
const textareaCls =
  'w-full border border-gray-200 rounded px-3 py-2 text-xs font-mono focus:outline-none focus:border-blue-400 resize-none'

function fillPrompt(template: string, role: string, focus: string, tone: string) {
  return template
    .split('{role}')
    .join(role || '')
    .split('{focus}')
    .join(focus || '')
    .split('{tone}')
    .join(tone || '')
}

function joinPromptSections(...parts: Array<string | null | undefined>) {
  return parts.map((part) => (part || '').trim()).filter(Boolean).join('\n\n')
}

export function SettingsModal({ onClose }: Props) {
  const { data: persona } = usePersona()
  const { data: status } = useOllamaStatus()
  const { data: accounts = [] } = useAccounts()
  const selectedAccountId = useUIStore((s) => s.selectedAccountId)
  const { language, setLanguage, t } = useI18n()
  const qc = useQueryClient()

  const models = status?.models ?? []

  const [role, setRole] = useState('')
  const [focus, setFocus] = useState('')
  const [tone, setTone] = useState<string>(getPromptTemplates(language).defaultTone)
  const [selectedModel, setSelectedModel] = useState('')
  const [syncInterval, setSyncInterval] = useState(2)
  const [selectedLanguage, setSelectedLanguage] = useState<AppLanguage>(language)
  const [analysisPrompt, setAnalysisPrompt] = useState<string | null>(null)
  const [replyPrompt, setReplyPrompt] = useState<string | null>(null)
  const [showPrompts, setShowPrompts] = useState(false)
  const [promptAccountId, setPromptAccountId] = useState<string>('')
  const [accountPromptContext, setAccountPromptContext] = useState('')

  useEffect(() => {
    if (persona) {
      const personaLanguage =
        persona.language === 'en-US' || persona.language === 'zh-CN' ? persona.language : 'en-US'
      setRole(persona.role || '')
      setFocus(persona.focus || '')
      setTone(persona.tone || getPromptTemplates(personaLanguage).defaultTone)
      setSelectedModel(persona.ollama_model || '')
      setSyncInterval(persona.sync_interval_hours ?? 2)
      setSelectedLanguage(personaLanguage)
      setAnalysisPrompt(persona.analysis_system_prompt)
      setReplyPrompt(persona.reply_system_prompt)
    }
  }, [persona])

  useEffect(() => {
    const currentDefaults = [
      getPromptTemplates('zh-CN').defaultTone,
      getPromptTemplates('en-US').defaultTone,
      '',
    ]
    if (currentDefaults.includes(tone)) {
      setTone(getPromptTemplates(selectedLanguage).defaultTone)
    }
  }, [selectedLanguage, tone])

  useEffect(() => {
    if (accounts.length === 0) {
      setPromptAccountId('')
      setAccountPromptContext('')
      return
    }

    const preferredId =
      (selectedAccountId && accounts.some((account) => account.id === selectedAccountId) && selectedAccountId) ||
      promptAccountId ||
      accounts[0].id
    const account = accounts.find((item) => item.id === preferredId) ?? accounts[0]
    setPromptAccountId(account.id)
    setAccountPromptContext(account.prompt_context || '')
  }, [accounts, promptAccountId, selectedAccountId])

  useEffect(() => {
    const account = accounts.find((item) => item.id === promptAccountId)
    setAccountPromptContext(account?.prompt_context || '')
  }, [accounts, promptAccountId])

  const promptTemplates = getPromptTemplates(selectedLanguage)
  const scheduleOptions = getScheduleOptions(selectedLanguage)

  const analysisPromptPreview = useMemo(
    () =>
      joinPromptSections(
        fillPrompt(promptTemplates.analysisPrefix, role, focus, tone),
        analysisPrompt,
        accountPromptContext,
        promptTemplates.analysisJsonSuffix,
      ),
    [accountPromptContext, analysisPrompt, focus, promptTemplates, role, tone],
  )

  const replyPromptPreview = useMemo(
    () =>
      joinPromptSections(
        fillPrompt(promptTemplates.replyPrompt, role, focus, tone),
        replyPrompt,
        accountPromptContext,
      ),
    [accountPromptContext, focus, promptTemplates, replyPrompt, role, tone],
  )

  const save = useMutation({
    mutationFn: async () => {
      await api.settings.updatePersona({
        role,
        focus,
        tone,
        ollama_model: selectedModel || null,
        sync_interval_hours: syncInterval,
        language: selectedLanguage,
        analysis_system_prompt: analysisPrompt === null ? '' : analysisPrompt,
        reply_system_prompt: replyPrompt === null ? '' : replyPrompt,
      })

      if (promptAccountId) {
        await api.accounts.update(promptAccountId, {
          prompt_context: accountPromptContext || null,
        })
      }
    },
    onSuccess: () => {
      setLanguage(selectedLanguage)
      qc.invalidateQueries({ queryKey: ['persona'] })
      qc.invalidateQueries({ queryKey: ['accounts'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="max-h-[90vh] w-[480px] overflow-y-auto rounded-xl bg-white p-5 shadow-xl space-y-5">
        <h3 className="font-semibold text-gray-800">{t('settingsTitle')}</h3>

        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            {t('settingsLanguageSection')}
          </div>
          <div>
            <label className={labelCls}>{t('settingsLanguageLabel')}</label>
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value as AppLanguage)}
              className={inputCls}
            >
              <option value="zh-CN">{t('settingsLanguageChinese')}</option>
              <option value="en-US">{t('settingsLanguageEnglish')}</option>
            </select>
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            {t('settingsPersonaSection')}
          </div>
          <p className="text-xs text-gray-500">{t('settingsPersonaHelp')}</p>
          <div>
            <label className={labelCls}>{t('settingsRole')}</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder={t('settingsRolePlaceholder')}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>{t('settingsFocus')}</label>
            <textarea
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder={t('settingsFocusPlaceholder')}
              rows={3}
              className={`${inputCls} resize-none`}
            />
          </div>
          <div>
            <label className={labelCls}>{t('settingsTone')}</label>
            <input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder={t('settingsTonePlaceholder')}
              className={inputCls}
            />
          </div>

          <div className="border border-dashed border-blue-200 rounded-lg bg-blue-50/40 px-3 py-2">
            <button
              type="button"
              onClick={() => setShowPrompts((v) => !v)}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 select-none font-medium"
            >
              <span>{showPrompts ? '▾' : '▸'}</span>
              {t('settingsCustomPrompts')}
            </button>
            {showPrompts && (
              <div className="mt-2 space-y-3 pl-3 border-l-2 border-gray-100">
                <p className="text-xs text-gray-500">
                  {t('settingsSupportsPlaceholders')}
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{role}'}</code>
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{focus}'}</code>
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{tone}'}</code>
                </p>
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <label className={labelCls}>{t('settingsAnalysisInstruction')}</label>
                    <button
                      type="button"
                      onClick={() => setAnalysisPrompt(null)}
                      className="text-xs text-gray-400 hover:text-blue-500"
                    >
                      {t('settingsRestoreDefault')}
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={analysisPrompt ?? ''}
                    onChange={(e) => setAnalysisPrompt(e.target.value)}
                    placeholder={t('settingsAnalysisInstructionPlaceholder')}
                    className={textareaCls}
                  />
                  <div className="mt-2">
                    <p className="text-xs text-gray-400 mb-1">{t('settingsAnalysisPromptReadonly')}</p>
                    <textarea
                      readOnly
                      rows={8}
                      value={analysisPromptPreview}
                      className="w-full cursor-not-allowed rounded border border-gray-100 bg-gray-50 px-3 py-2 text-xs font-mono text-gray-500 resize-none"
                    />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <label className={labelCls}>{t('settingsReplyInstruction')}</label>
                    <button
                      type="button"
                      onClick={() => setReplyPrompt(null)}
                      className="text-xs text-gray-400 hover:text-blue-500"
                    >
                      {t('settingsRestoreDefault')}
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={replyPrompt ?? ''}
                    onChange={(e) => setReplyPrompt(e.target.value)}
                    placeholder={t('settingsReplyInstructionPlaceholder')}
                    className={textareaCls}
                  />
                  <div className="mt-2">
                    <p className="text-xs text-gray-400 mb-1">{t('settingsReplyPromptReadonly')}</p>
                    <textarea
                      readOnly
                      rows={8}
                      value={replyPromptPreview}
                      className="w-full cursor-not-allowed rounded border border-gray-100 bg-gray-50 px-3 py-2 text-xs font-mono text-gray-500 resize-none"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            {t('settingsAccountPromptSection')}
          </div>
          <p className="text-xs text-gray-500">{t('settingsAccountPromptHelp')}</p>
          <div>
            <label className={labelCls}>{t('settingsAccountPromptAccount')}</label>
            <select
              value={promptAccountId}
              onChange={(e) => setPromptAccountId(e.target.value)}
              className={inputCls}
              disabled={accounts.length === 0}
            >
              {accounts.length === 0 ? (
                <option value="">{t('settingsAccountPromptNoAccounts')}</option>
              ) : (
                accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.display_name || account.email}
                  </option>
                ))
              )}
            </select>
          </div>
          <div>
            <label className={labelCls}>{t('settingsAccountPromptLabel')}</label>
            <textarea
              rows={4}
              value={accountPromptContext}
              onChange={(e) => setAccountPromptContext(e.target.value)}
              placeholder={t('settingsAccountPromptPlaceholder')}
              className={`${inputCls} resize-none`}
              disabled={!promptAccountId}
            />
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            {t('settingsModelSection')}
          </div>
          <div>
            <label className={labelCls}>{t('settingsModelLabel')}</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className={inputCls}
            >
              {!selectedModel && <option value="">{t('settingsSelectModel')}</option>}
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            {models.length === 0 && <p className="mt-1 text-xs text-gray-400">{t('settingsNoModels')}</p>}
          </div>
        </div>

        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            {t('settingsScheduleSection')}
          </div>
          <div>
            <label className={labelCls}>{t('settingsScheduleLabel')}</label>
            <select
              value={syncInterval}
              onChange={(e) => setSyncInterval(Number(e.target.value))}
              className={inputCls}
            >
              {scheduleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">{t('settingsScheduleHelp')}</p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5">
            {t('commonCancel')}
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-1.5"
          >
            {save.isPending ? t('commonSaving') : t('commonSave')}
          </button>
        </div>

        {save.isError && <p className="text-xs text-red-500 text-right">{t('settingsSaveFailed')}</p>}
      </div>
    </div>
  )
}
