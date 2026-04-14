import { useEffect } from 'react'
import { useI18n } from '../../i18n'
import { useOllamaStatus, usePendingCount, usePersona, useTriggerAI } from '../../hooks/useEmails'
import { useUIStore } from '../../store/uiStore'

function StatusDot({
  running,
  processing,
  sleepingTitle,
  processingTitle,
  runningTitle,
}: {
  running: boolean
  processing: boolean
  sleepingTitle: string
  processingTitle: string
  runningTitle: string
}) {
  if (!running) return <span title={sleepingTitle}>⚪️</span>
  if (processing) return <span title={processingTitle}>🟡</span>
  return <span title={runningTitle}>🟢</span>
}

export function AIConsole() {
  const { data: status } = useOllamaStatus()
  const selectedAccountId = useUIStore((s) => s.selectedAccountId)
  const { data: accountPendingData } = usePendingCount(selectedAccountId)
  const { data: globalPendingData } = usePendingCount()
  const { data: persona } = usePersona()
  const trigger = useTriggerAI()
  const { t } = useI18n()

  const accountPending = accountPendingData?.pending ?? 0
  const globalPending = globalPendingData?.pending ?? 0
  const running = status?.running ?? false
  const processing = status?.is_processing ?? false
  const queueSize = status?.queue_size ?? 0
  const models = status?.models ?? []

  const selectedModel = persona?.ollama_model || ''
  const modelOK = selectedModel !== '' && models.includes(selectedModel)

  useEffect(() => {
    if (trigger.data && !processing && globalPending === 0) {
      trigger.reset()
    }
  }, [processing, globalPending, trigger])

  const statusText = !running
    ? t('aiConsoleOllamaStopped')
    : models.length === 0
      ? t('aiConsoleLoadingModels')
      : !selectedModel
        ? t('aiConsoleSelectModel')
        : !modelOK
          ? t('aiConsoleModelMissing')
          : processing
            ? t('aiConsoleProcessingQueue', { count: queueSize })
            : t('aiConsoleReady')

  return (
    <div className="border-t border-gray-200 p-3 space-y-2">
      <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">
        {t('aiConsoleTitle')}
      </div>
      <div className="flex items-center gap-2 text-sm">
        <StatusDot
          running={running}
          processing={processing}
          sleepingTitle={t('aiStatusSleeping')}
          processingTitle={t('aiStatusProcessing')}
          runningTitle={t('aiStatusRunning')}
        />
        <span className={`text-gray-600 text-xs ${!modelOK && running ? 'text-orange-500' : ''}`}>
          {statusText}
        </span>
      </div>

      {globalPending > 0 && (
        <div className="text-xs text-gray-500">
          {t('aiConsolePendingInline', { account: accountPending, global: globalPending })}
        </div>
      )}
      <button
        onClick={() => trigger.mutate()}
        disabled={trigger.isPending || processing || !running || !modelOK}
        className="w-full text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-2 py-1.5 transition-colors"
      >
        {trigger.isPending ? t('aiConsoleTriggering') : t('aiConsoleTrigger')}
      </button>
      {trigger.data && (
        <div className="text-xs text-green-600">
          {trigger.data.queued_count > 0
            ? t('aiConsoleQueued', { count: trigger.data.queued_count })
            : t('aiConsoleNoPending')}
        </div>
      )}
    </div>
  )
}
