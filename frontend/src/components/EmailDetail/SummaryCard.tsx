import { useI18n } from '../../i18n'

interface Props {
  summary: string
  importance: number | null
}

export function SummaryCard({ summary, importance }: Props) {
  const { t } = useI18n()

  return (
    <div className="mx-4 mt-3 mb-2 p-3 bg-blue-50 rounded-lg border border-blue-100 text-sm">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-blue-600 font-medium text-xs uppercase tracking-wide">{t('summaryTitle')}</span>
        {importance != null && (
          <span
            className={`text-xs px-1.5 py-0.5 rounded font-medium ${
              importance >= 4
                ? 'bg-red-100 text-red-600'
                : importance >= 3
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-gray-100 text-gray-500'
            }`}
          >
            {t('summaryImportance', { score: importance })}
          </span>
        )}
      </div>
      <p className="text-gray-700 leading-relaxed">{summary}</p>
    </div>
  )
}
