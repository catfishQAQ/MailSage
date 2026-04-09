import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { usePersona } from './hooks/useEmails'

export type AppLanguage = 'zh-CN' | 'en-US'

type Dictionary = typeof dictionaries['zh-CN']

const dictionaries = {
  'zh-CN': {
    appName: 'MailSage',
    commonLoading: '加载中…',
    commonLoadFailed: '加载失败',
    commonCancel: '取消',
    commonSave: '保存',
    commonSaving: '保存中…',
    commonDone: '完成',
    commonAdd: '添加',
    commonAdding: '添加中…',
    commonDelete: '删除',
    commonRetry: '重试',
    commonNoneBody: '（无正文）',
    sidebarAllInboxes: '📥 所有收件箱',
    sidebarImportant: '⚡️ 重要邮件',
    sidebarAccounts: '账号',
    sidebarAddAccountTitle: '添加账号',
    sidebarUpdatePasswordPrompt: '更新 {email} 的授权码：',
    sidebarUpdatePasswordTitle: '更新授权码',
    sidebarSyncTitle: '同步',
    sidebarDeleteConfirm: '删除账号 {email}？相关邮件也会一并删除。',
    sidebarDeleteTitle: '删除账号',
    sidebarSettings: '⚙️ 设置',
    aiStatusSleeping: '休眠',
    aiStatusProcessing: '处理中',
    aiStatusRunning: '运行中',
    aiConsoleTitle: 'AI 控制台',
    aiConsoleOllamaStopped: 'Ollama 未运行',
    aiConsoleLoadingModels: '正在获取模型列表…',
    aiConsoleSelectModel: '请在设置中选择模型',
    aiConsoleModelMissing: '模型未找到',
    aiConsoleReady: '就绪',
    aiConsoleProcessingQueue: '处理中 (队列 {count})',
    aiConsolePending: '待处理 {count} 封',
    aiConsoleTrigger: '⚡️ 批量处理未读邮件',
    aiConsoleTriggering: '加入队列中…',
    aiConsoleQueued: '已将 {count} 封邮件加入 AI 队列',
    aiConsoleNoPending: '没有待处理邮件',
    emailListEmpty: '收件箱为空',
    emailListEmptyImportant: '没有重要邮件',
    emailListTotal: '共 {count} 封',
    emailListTotalImportantSuffix: ' · 仅重要',
    emailListImportantTitle: 'AI 判定为重要',
    emailListPendingTitle: '待 AI 处理',
    emailListProcessingTitle: 'AI 处理中',
    emailDetailEmpty: '选择一封邮件以查看详情',
    emailDetailAnalyze: '🤖 AI 分析',
    emailDetailAnalyzing: '分析中…',
    emailDetailReanalyze: '↺ 重新分析',
    emailDetailReanalyzeTitle: '重新分析',
    emailDetailSender: '发件人：',
    emailDetailTime: '时间：',
    emailDetailAiProcessing: 'AI 正在分析中…',
    emailDetailAiFailed:
      'AI 分析失败。请在左侧 AI 控制台确认 Ollama 已运行并选择正确模型，然后点击“↺ 重新分析”重试。',
    summaryTitle: 'AI 摘要',
    summaryImportance: '重要性 {score}/5',
    summaryActionItems: '待办事项',
    replyTitle: '回复',
    replyPlaceholder: '输入回复草稿…',
    replyPolish: '✨ AI 润色 / 扩写',
    replyPolishing: '润色中…',
    replyEditAgain: '重新编辑',
    replySend: '发送',
    replySending: '发送中…',
    replySent: '✓ 已发送',
    replyExpandFailed: '扩写失败，请检查 Ollama 是否运行',
    replySendFailed: '发送失败，请检查账号配置',
    addAccountTitle: '添加邮箱账号',
    addAccountSuccess: '账号添加成功',
    addAccountSyncing: '正在后台触发首次同步（约拉取最近 200 封）',
    addAccountEmail: '邮箱',
    addAccountId: '账号 ID（备用）',
    addAccountEmailLabel: '邮箱地址 *',
    addAccountEmailHelp: '输入邮箱后失焦，自动填充 IMAP/SMTP 配置',
    addAccountDisplayName: '显示名称（可选）',
    addAccountDisplayNamePlaceholder: '例：我的工作邮箱',
    addAccountPassword: '授权码 / 应用专用密码 *',
    addAccountPasswordPlaceholder: '非登录密码，需在邮箱设置中生成',
    addAccountImapSettings: 'IMAP 设置',
    addAccountImapServer: 'IMAP 服务器 *',
    addAccountPort: '端口',
    addAccountSmtpSettings: 'SMTP 设置',
    addAccountSmtpServer: 'SMTP 服务器 *',
    addAccountExists: '该邮箱已添加',
    settingsTitle: '设置',
    settingsLanguageSection: '语言',
    settingsLanguageLabel: '界面语言',
    settingsLanguageChinese: '中文',
    settingsLanguageEnglish: 'English',
    settingsPersonaSection: '身份预设',
    settingsPersonaHelp: '此信息作为 System Prompt 注入每次 AI 分析，影响重要性判断和回复语气。',
    settingsRole: '职业角色',
    settingsRolePlaceholder: '例：计算机视觉与机器学习研究员',
    settingsFocus: '关注领域',
    settingsFocusPlaceholder: '例：自动驾驶模型的对抗性攻击、VAEs 架构调试',
    settingsTone: '语气偏好',
    settingsTonePlaceholder: '例：专业、客观、直接',
    settingsCustomPrompts: '自定义 AI 提示词',
    settingsSupportsPlaceholders: '支持占位符：',
    settingsAnalysisInstruction: '邮件分析指令',
    settingsReplyInstruction: '草稿扩写指令',
    settingsRestoreDefault: '恢复默认',
    settingsFixedSuffix: '固定追加（不可修改）：',
    settingsModelSection: 'AI 模型',
    settingsModelLabel: '使用模型',
    settingsSelectModel: '— 请选择模型 —',
    settingsNoModels: 'Ollama 未运行或无可用模型',
    settingsScheduleSection: '定时同步',
    settingsScheduleLabel: '同步频率',
    settingsScheduleHelp: '每次同步后将自动触发 AI 分析新邮件',
    settingsSaveFailed: '保存失败，请重试',
    scheduleManual: '手动启动',
    scheduleEveryHours: '每 {hours} 小时',
    scheduleDaily: '每天一次',
    promptDefaultTone: '专业、客观、直接',
    promptAnalysisPrefix: '你是邮件助手。角色：{role}，关注：{focus}。语气：{tone}。',
    promptReply: '你是专业邮件写作助手。你的身份：{role}。语气要求：{tone}。\n请将用户提供的草稿扩写为一封结构完整、语气专业的回复邮件。\n只输出邮件正文，不要包含主题行、称谓等格式提示语。',
    promptAnalysisJsonSuffix:
      '分析邮件后，仅输出以下格式的纯JSON（不加任何额外文字）：\n{"importance_score":1-5,"is_important":true/false,"summary":"一句话核心摘要","action_items":["待办1","待办2"],"ghost_reply_suggestion":"一句话回复建议"}',
  },
  'en-US': {
    appName: 'MailSage',
    commonLoading: 'Loading…',
    commonLoadFailed: 'Failed to load',
    commonCancel: 'Cancel',
    commonSave: 'Save',
    commonSaving: 'Saving…',
    commonDone: 'Done',
    commonAdd: 'Add',
    commonAdding: 'Adding…',
    commonDelete: 'Delete',
    commonRetry: 'Retry',
    commonNoneBody: '(No body)',
    sidebarAllInboxes: '📥 All Inboxes',
    sidebarImportant: '⚡️ Important',
    sidebarAccounts: 'Accounts',
    sidebarAddAccountTitle: 'Add account',
    sidebarUpdatePasswordPrompt: 'Update the app password for {email}:',
    sidebarUpdatePasswordTitle: 'Update app password',
    sidebarSyncTitle: 'Sync',
    sidebarDeleteConfirm: 'Delete account {email}? Related emails will also be removed.',
    sidebarDeleteTitle: 'Delete account',
    sidebarSettings: '⚙️ Settings',
    aiStatusSleeping: 'Sleeping',
    aiStatusProcessing: 'Processing',
    aiStatusRunning: 'Running',
    aiConsoleTitle: 'AI Console',
    aiConsoleOllamaStopped: 'Ollama is not running',
    aiConsoleLoadingModels: 'Loading model list…',
    aiConsoleSelectModel: 'Select a model in Settings',
    aiConsoleModelMissing: 'Model not found',
    aiConsoleReady: 'Ready',
    aiConsoleProcessingQueue: 'Processing (queue {count})',
    aiConsolePending: '{count} pending',
    aiConsoleTrigger: '⚡️ Process unread emails',
    aiConsoleTriggering: 'Queueing…',
    aiConsoleQueued: 'Queued {count} emails for AI processing',
    aiConsoleNoPending: 'No pending emails',
    emailListEmpty: 'Inbox is empty',
    emailListEmptyImportant: 'No important emails',
    emailListTotal: '{count} emails',
    emailListTotalImportantSuffix: ' · Important only',
    emailListImportantTitle: 'Marked important by AI',
    emailListPendingTitle: 'Waiting for AI',
    emailListProcessingTitle: 'AI processing',
    emailDetailEmpty: 'Select an email to view details',
    emailDetailAnalyze: '🤖 Analyze',
    emailDetailAnalyzing: 'Analyzing…',
    emailDetailReanalyze: '↺ Reanalyze',
    emailDetailReanalyzeTitle: 'Reanalyze',
    emailDetailSender: 'From: ',
    emailDetailTime: 'Time: ',
    emailDetailAiProcessing: 'AI is analyzing this email…',
    emailDetailAiFailed:
      'AI analysis failed. Check the AI Console to make sure Ollama is running and the correct model is selected, then try “↺ Reanalyze” again.',
    summaryTitle: 'AI Summary',
    summaryImportance: 'Importance {score}/5',
    summaryActionItems: 'Action items',
    replyTitle: 'Reply',
    replyPlaceholder: 'Write a reply draft…',
    replyPolish: '✨ Polish / expand with AI',
    replyPolishing: 'Polishing…',
    replyEditAgain: 'Edit again',
    replySend: 'Send',
    replySending: 'Sending…',
    replySent: '✓ Sent',
    replyExpandFailed: 'Expansion failed. Check whether Ollama is running.',
    replySendFailed: 'Sending failed. Check the account settings.',
    addAccountTitle: 'Add email account',
    addAccountSuccess: 'Account added',
    addAccountSyncing: 'Triggering the first sync in the background (about the latest 200 emails)',
    addAccountEmail: 'Email',
    addAccountId: 'Account ID (backup)',
    addAccountEmailLabel: 'Email address *',
    addAccountEmailHelp: 'After the email field loses focus, IMAP/SMTP settings are auto-filled',
    addAccountDisplayName: 'Display name (optional)',
    addAccountDisplayNamePlaceholder: 'Example: My work inbox',
    addAccountPassword: 'App password / authorization code *',
    addAccountPasswordPlaceholder: 'Not your login password. Generate it in your mailbox settings.',
    addAccountImapSettings: 'IMAP Settings',
    addAccountImapServer: 'IMAP server *',
    addAccountPort: 'Port',
    addAccountSmtpSettings: 'SMTP Settings',
    addAccountSmtpServer: 'SMTP server *',
    addAccountExists: 'This email has already been added',
    settingsTitle: 'Settings',
    settingsLanguageSection: 'Language',
    settingsLanguageLabel: 'Interface language',
    settingsLanguageChinese: '中文',
    settingsLanguageEnglish: 'English',
    settingsPersonaSection: 'Persona',
    settingsPersonaHelp: 'This information is injected into each AI analysis as the system prompt and influences importance judgments and reply tone.',
    settingsRole: 'Role',
    settingsRolePlaceholder: 'Example: Computer vision and machine learning researcher',
    settingsFocus: 'Focus',
    settingsFocusPlaceholder: 'Example: Adversarial attacks on autonomous driving models, VAE debugging',
    settingsTone: 'Tone preference',
    settingsTonePlaceholder: 'Example: professional, objective, direct',
    settingsCustomPrompts: 'Custom AI prompts',
    settingsSupportsPlaceholders: 'Supported placeholders:',
    settingsAnalysisInstruction: 'Email analysis instruction',
    settingsReplyInstruction: 'Reply expansion instruction',
    settingsRestoreDefault: 'Restore default',
    settingsFixedSuffix: 'Fixed suffix (read-only):',
    settingsModelSection: 'AI Model',
    settingsModelLabel: 'Selected model',
    settingsSelectModel: '— Select a model —',
    settingsNoModels: 'Ollama is not running or no models are available',
    settingsScheduleSection: 'Schedule',
    settingsScheduleLabel: 'Sync frequency',
    settingsScheduleHelp: 'Each sync automatically triggers AI analysis for new emails',
    settingsSaveFailed: 'Save failed. Please try again.',
    scheduleManual: 'Manual only',
    scheduleEveryHours: 'Every {hours} hour(s)',
    scheduleDaily: 'Once per day',
    promptDefaultTone: 'professional, objective, direct',
    promptAnalysisPrefix: 'You are an email assistant. Role: {role}. Focus: {focus}. Tone: {tone}.',
    promptReply: 'You are a professional email writing assistant. Your role is {role}. Required tone: {tone}.\nExpand the user draft into a complete, professional reply email.\nOutput only the email body. Do not include a subject line or formatting instructions.',
    promptAnalysisJsonSuffix:
      'After analyzing the email, output only pure JSON in this format (no extra text):\n{"importance_score":1-5,"is_important":true/false,"summary":"One-sentence summary","action_items":["Action item 1","Action item 2"],"ghost_reply_suggestion":"One-sentence reply suggestion"}',
  },
} as const

interface I18nContextValue {
  language: AppLanguage
  setLanguage: (language: AppLanguage) => void
  t: (key: keyof Dictionary, vars?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function interpolate(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? ''))
}

export function getPromptTemplates(language: AppLanguage) {
  return {
    analysisPrefix: dictionaries[language].promptAnalysisPrefix,
    replyPrompt: dictionaries[language].promptReply,
    analysisJsonSuffix: dictionaries[language].promptAnalysisJsonSuffix,
    defaultTone: dictionaries[language].promptDefaultTone,
  }
}

export function getScheduleOptions(language: AppLanguage) {
  const dict = dictionaries[language]
  return [
    { value: 0, label: dict.scheduleManual },
    { value: 1, label: interpolate(dict.scheduleEveryHours, { hours: 1 }) },
    { value: 2, label: interpolate(dict.scheduleEveryHours, { hours: 2 }) },
    { value: 4, label: interpolate(dict.scheduleEveryHours, { hours: 4 }) },
    { value: 6, label: interpolate(dict.scheduleEveryHours, { hours: 6 }) },
    { value: 12, label: interpolate(dict.scheduleEveryHours, { hours: 12 }) },
    { value: 24, label: dict.scheduleDaily },
  ]
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const { data: persona } = usePersona()
  const [language, setLanguageState] = useState<AppLanguage>('en-US')

  useEffect(() => {
    if (persona?.language === 'en-US' || persona?.language === 'zh-CN') {
      setLanguageState(persona.language)
    }
  }, [persona?.language])

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage: setLanguageState,
      t: (key, vars) => interpolate(dictionaries[language][key], vars),
    }),
    [language],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider')
  }
  return context
}
