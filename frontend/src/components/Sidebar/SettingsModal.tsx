import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { usePersona, useOllamaStatus } from '../../hooks/useEmails'
import { api } from '../../api'

interface Props {
  onClose: () => void
}

const INTERVAL_OPTIONS = [
  { value: 0,  label: '手动启动' },
  { value: 1,  label: '每 1 小时' },
  { value: 2,  label: '每 2 小时' },
  { value: 4,  label: '每 4 小时' },
  { value: 6,  label: '每 6 小时' },
  { value: 12, label: '每 12 小时' },
  { value: 24, label: '每天一次' },
]

const DEFAULT_ANALYSIS_PROMPT = '你是邮件助手。角色：{role}，关注：{focus}。语气：{tone}。'
const DEFAULT_REPLY_PROMPT = '你是专业邮件写作助手。你的身份：{role}。语气要求：{tone}。\n请将用户提供的草稿扩写为一封结构完整、语气专业的回复邮件。\n只输出邮件正文，不要包含主题行、称谓等格式提示语。'
const ANALYSIS_JSON_SUFFIX = `分析邮件后，仅输出以下格式的纯JSON（不加任何额外文字）：\n{"importance_score":1-5,"is_important":true/false,"summary":"一句话核心摘要","action_items":["待办1","待办2"],"ghost_reply_suggestion":"一句话回复建议"}`

const inputCls = 'w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400'
const labelCls = 'block text-xs font-medium text-gray-600 mb-1'
const textareaCls = 'w-full border border-gray-200 rounded px-3 py-2 text-xs font-mono focus:outline-none focus:border-blue-400 resize-none'

export function SettingsModal({ onClose }: Props) {
  const { data: persona } = usePersona()
  const { data: status } = useOllamaStatus()
  const qc = useQueryClient()

  const models = status?.models ?? []

  const [role, setRole] = useState('')
  const [focus, setFocus] = useState('')
  const [tone, setTone] = useState('专业、客观、直接')
  const [selectedModel, setSelectedModel] = useState('')
  const [syncInterval, setSyncInterval] = useState(2)
  const [analysisPrompt, setAnalysisPrompt] = useState<string | null>(null)
  const [replyPrompt, setReplyPrompt] = useState<string | null>(null)
  const [showPrompts, setShowPrompts] = useState(false)

  useEffect(() => {
    if (persona) {
      setRole(persona.role || '')
      setFocus(persona.focus || '')
      setTone(persona.tone || '专业、客观、直接')
      setSelectedModel(persona.ollama_model || '')
      setSyncInterval(persona.sync_interval_hours ?? 2)
      setAnalysisPrompt(persona.analysis_system_prompt)
      setReplyPrompt(persona.reply_system_prompt)
    }
  }, [persona?.id])

  const save = useMutation({
    mutationFn: () =>
      api.settings.updatePersona({
        role,
        focus,
        tone,
        ollama_model: selectedModel || null,
        sync_interval_hours: syncInterval,
        analysis_system_prompt: analysisPrompt === null ? '' : analysisPrompt,
        reply_system_prompt: replyPrompt === null ? '' : replyPrompt,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['persona'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-[420px] p-5 space-y-5 max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold text-gray-800">设置</h3>

        {/* 身份预设 */}
        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            身份预设 · Persona
          </div>
          <p className="text-xs text-gray-500">
            此信息作为 System Prompt 注入每次 AI 分析，影响重要性判断和回复语气。
          </p>
          <div>
            <label className={labelCls}>职业角色</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="例：计算机视觉与机器学习研究员"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>关注领域</label>
            <textarea
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="例：自动驾驶模型的对抗性攻击、VAEs 架构调试"
              rows={3}
              className={`${inputCls} resize-none`}
            />
          </div>
          <div>
            <label className={labelCls}>语气偏好</label>
            <input
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="例：专业、客观、直接"
              className={inputCls}
            />
          </div>

          {/* 自定义 AI 提示词（可折叠） */}
          <div className="border border-dashed border-blue-200 rounded-lg bg-blue-50/40 px-3 py-2">
            <button
              type="button"
              onClick={() => setShowPrompts((v) => !v)}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 select-none font-medium"
            >
              <span>{showPrompts ? '▾' : '▸'}</span>
              自定义 AI 提示词
            </button>
            {showPrompts && (
              <div className="mt-2 space-y-3 pl-3 border-l-2 border-gray-100">
                <p className="text-xs text-gray-500">
                  支持占位符：
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{role}'}</code>
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{focus}'}</code>
                  <code className="bg-gray-100 px-1 rounded mx-0.5">{'{tone}'}</code>
                </p>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className={labelCls}>邮件分析指令</label>
                    <button
                      type="button"
                      onClick={() => setAnalysisPrompt(null)}
                      className="text-xs text-gray-400 hover:text-blue-500"
                    >
                      恢复默认
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={analysisPrompt ?? DEFAULT_ANALYSIS_PROMPT}
                    onChange={(e) => setAnalysisPrompt(e.target.value)}
                    className={textareaCls}
                  />
                  <div className="mt-2">
                    <p className="text-xs text-gray-400 mb-1">固定追加（不可修改）：</p>
                    <textarea
                      readOnly
                      rows={3}
                      value={ANALYSIS_JSON_SUFFIX}
                      className="w-full border border-gray-100 rounded px-3 py-2 text-xs font-mono bg-gray-50 text-gray-400 resize-none cursor-not-allowed"
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className={labelCls}>草稿扩写指令</label>
                    <button
                      type="button"
                      onClick={() => setReplyPrompt(null)}
                      className="text-xs text-gray-400 hover:text-blue-500"
                    >
                      恢复默认
                    </button>
                  </div>
                  <textarea
                    rows={4}
                    value={replyPrompt ?? DEFAULT_REPLY_PROMPT}
                    onChange={(e) => setReplyPrompt(e.target.value)}
                    className={textareaCls}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* AI 模型 */}
        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            AI 模型 · Model
          </div>
          <div>
            <label className={labelCls}>使用模型</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className={inputCls}
            >
              {!selectedModel && <option value="">— 请选择模型 —</option>}
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            {models.length === 0 && (
              <p className="text-xs text-gray-400 mt-1">Ollama 未运行或无可用模型</p>
            )}
          </div>
        </div>

        {/* 定时同步 */}
        <div className="space-y-3">
          <div className="text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100 pb-1">
            定时同步 · Schedule
          </div>
          <div>
            <label className={labelCls}>同步频率</label>
            <select
              value={syncInterval}
              onChange={(e) => setSyncInterval(Number(e.target.value))}
              className={inputCls}
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              每次同步后将自动触发 AI 分析新邮件
            </p>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex justify-end gap-2 pt-1">
          <button
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5"
          >
            取消
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-4 py-1.5"
          >
            {save.isPending ? '保存中…' : '保存'}
          </button>
        </div>

        {save.isError && (
          <p className="text-xs text-red-500 text-right">保存失败，请重试</p>
        )}
      </div>
    </div>
  )
}
