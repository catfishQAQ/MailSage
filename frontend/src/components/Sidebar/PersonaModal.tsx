import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { usePersona } from '../../hooks/useEmails'
import { api } from '../../api'

interface Props {
  onClose: () => void
}

export function PersonaModal({ onClose }: Props) {
  const { data: persona } = usePersona()
  const qc = useQueryClient()
  const [role, setRole] = useState(persona?.role || '')
  const [focus, setFocus] = useState(persona?.focus || '')
  const [tone, setTone] = useState(persona?.tone || '专业、客观、直接')

  const save = useMutation({
    mutationFn: () => api.settings.updatePersona({ role, focus, tone }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['persona'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-96 p-5 space-y-4">
        <h3 className="font-semibold text-gray-800">全局身份预设 (Persona)</h3>
        <p className="text-xs text-gray-500">此信息作为 System Prompt 注入每次 AI 分析，影响重要性判断和回复语气。</p>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">职业角色</label>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="例：计算机视觉与机器学习研究员"
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">关注领域</label>
          <textarea
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="例：自动驾驶模型的对抗性攻击、VAEs 架构调试"
            rows={3}
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm resize-none focus:outline-none focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">语气偏好</label>
          <input
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            placeholder="例：专业、客观、直接"
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5">
            取消
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-1.5"
          >
            {save.isPending ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
