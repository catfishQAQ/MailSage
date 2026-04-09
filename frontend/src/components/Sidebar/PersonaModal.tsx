import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import { getPromptTemplates, useI18n } from '../../i18n'
import { usePersona } from '../../hooks/useEmails'

interface Props {
  onClose: () => void
}

export function PersonaModal({ onClose }: Props) {
  const { data: persona } = usePersona()
  const { language, t } = useI18n()
  const qc = useQueryClient()
  const [role, setRole] = useState(persona?.role || '')
  const [focus, setFocus] = useState(persona?.focus || '')
  const [tone, setTone] = useState(persona?.tone || getPromptTemplates(language).defaultTone)

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
        <h3 className="font-semibold text-gray-800">{t('settingsPersonaSection')}</h3>
        <p className="text-xs text-gray-500">{t('settingsPersonaHelp')}</p>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t('settingsRole')}</label>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder={t('settingsRolePlaceholder')}
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t('settingsFocus')}</label>
          <textarea
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder={t('settingsFocusPlaceholder')}
            rows={3}
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm resize-none focus:outline-none focus:border-blue-400"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t('settingsTone')}</label>
          <input
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            placeholder={t('settingsTonePlaceholder')}
            className="w-full border border-gray-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5">
            {t('commonCancel')}
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="text-sm bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-1.5"
          >
            {save.isPending ? t('commonSaving') : t('commonSave')}
          </button>
        </div>
      </div>
    </div>
  )
}
