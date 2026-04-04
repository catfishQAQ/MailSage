import { useOllamaStatus, useTriggerAI, usePendingCount, usePersona } from '../../hooks/useEmails'

function StatusDot({ running, processing }: { running: boolean; processing: boolean }) {
  if (!running) return <span title="休眠">⚪️</span>
  if (processing) return <span title="处理中">🟡</span>
  return <span title="运行中">🟢</span>
}

export function AIConsole() {
  const { data: status } = useOllamaStatus()
  const { data: pendingData } = usePendingCount()
  const { data: persona } = usePersona()
  const trigger = useTriggerAI()

  const pending = pendingData?.pending ?? 0
  const running = status?.running ?? false
  const processing = status?.is_processing ?? false
  const queueSize = status?.queue_size ?? 0
  const models = status?.models ?? []

  const selectedModel = persona?.ollama_model || ''
  const modelOK = selectedModel !== '' && models.includes(selectedModel)

  const statusText = !running
    ? 'Ollama 未运行'
    : models.length === 0
    ? '正在获取模型列表…'
    : !selectedModel
    ? '请在设置中选择模型'
    : !modelOK
    ? '模型未找到'
    : processing
    ? `处理中 (队列 ${queueSize})`
    : '就绪'

  return (
    <div className="border-t border-gray-200 p-3 space-y-2">
      <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">AI 控制台</div>
      <div className="flex items-center gap-2 text-sm">
        <StatusDot running={running} processing={processing} />
        <span className={`text-gray-600 text-xs ${!modelOK && running ? 'text-orange-500' : ''}`}>
          {statusText}
        </span>
      </div>

      {pending > 0 && (
        <div className="text-xs text-gray-500">
          待处理 <span className="font-semibold text-gray-700">{pending}</span> 封
        </div>
      )}
      <button
        onClick={() => trigger.mutate()}
        disabled={trigger.isPending || processing || !running || !modelOK}
        className="w-full text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded px-2 py-1.5 transition-colors"
      >
        {trigger.isPending ? '加入队列中…' : '⚡️ 批量处理未读邮件'}
      </button>
      {trigger.data && (
        <div className="text-xs text-green-600">{trigger.data.message}</div>
      )}
    </div>
  )
}
