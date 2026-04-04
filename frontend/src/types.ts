export type AIStatus = 'pending' | 'processing' | 'completed' | 'failed'

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
}

export interface EmailListItem {
  id: string
  account_id: string
  sender: string
  sender_name: string | null
  subject: string
  receive_time: string
  is_read: boolean
  has_attachments: boolean
  ai_status: AIStatus
  ai_importance: number | null
  ai_is_important: boolean | null
  ai_summary: string | null
}

export interface EmailDetail extends EmailListItem {
  recipients: string | null
  body_text: string | null
  body_html: string | null
  folder: string
  ai_action_items: string | null  // JSON array 字符串
  ai_ghost_reply: string | null
}

export interface EmailListResponse {
  items: EmailListItem[]
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
