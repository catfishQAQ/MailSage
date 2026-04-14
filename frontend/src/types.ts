export type AIStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type MailboxView = 'all' | 'important' | 'unread' | 'sent'
export type SentReplySource = 'local' | 'synced'

export interface Account {
  id: string
  email: string
  display_name: string | null
  imap_host: string
  imap_port: number
  smtp_host: string
  smtp_port: number
  is_active: boolean
  last_uid: number
  prompt_context: string | null
}

export interface EmailListItem {
  id: string
  message_id: string | null
  account_id: string
  sender: string
  sender_name: string | null
  subject: string
  receive_time: string
  is_read: boolean
  has_attachments: boolean
  folder: string
  ai_status: AIStatus
  ai_importance: number | null
  ai_is_important: boolean | null
  ai_summary: string | null
}

export interface SentReply {
  id: string
  account_id: string
  source_email_id: string
  message_id: string
  recipient: string
  subject: string | null
  body_text: string
  sent_at: string
  source: SentReplySource
}

export interface EmailDetail extends EmailListItem {
  recipients: string | null
  body_text: string | null
  body_html: string | null
  folders: string[]
  ai_ghost_reply: string | null
  sent_replies: SentReply[]
}

export interface EmailListResponse {
  items: EmailListItem[]
  total: number
  page: number
  page_size: number
}

export interface SentReplyListResponse {
  items: SentReply[]
  total: number
  page: number
  page_size: number
}

export interface Persona {
  id: number
  role: string | null
  focus: string | null
  tone: string | null
  ollama_model: string | null
  sync_interval_hours: number | null
  language: 'zh-CN' | 'en-US' | null
  analysis_system_prompt: string | null
  reply_system_prompt: string | null
}

export interface OllamaStatus {
  running: boolean
  model_available: boolean
  models: string[]
  queue_size: number
  is_processing: boolean
}

export interface AIStatusEvent {
  email_id: string
  ai_status: AIStatus
  ai_importance?: number
  ai_is_important?: boolean
  ai_summary?: string
  ai_ghost_reply?: string
}
