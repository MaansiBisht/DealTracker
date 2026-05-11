// Mirrors web/schemas.py — keep in lockstep when the Python contract changes.

export type JobKind = 'product' | 'hotel';
export type AlertType = 'stock' | 'price' | 'price_drop';
export type JobStatus =
  | 'pending'
  | 'running'
  | 'idle'
  | 'alerted'
  | 'stopped'
  | 'error';

export interface Job {
  id: string;
  // Owner. May be null for legacy orphans an admin can still see.
  user_id: string | null;
  kind: JobKind;
  url: string;
  email: string | null;
  webhook_url: string | null;
  telegram_chat_id: string | null;
  alert_type: AlertType;
  threshold: number | null;
  platform: string;
  status: JobStatus;

  last_status: string | null;
  last_price: string | null;
  last_checked_at: string | null;
  alerted_at: string | null;

  active: boolean;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
  is_admin: boolean;
  telegram_chat_id: string | null;
  telegram_display_name: string | null;
}

export interface AuthMeResponse {
  user: User;
  telegram_bot_username: string | null;
  telegram_bot_configured: boolean;
}

export interface TelegramConnection {
  paired: boolean;
  chat_id: string | null;
  display_name: string | null;
}

export interface JobCreatePayload {
  url: string;
  email: string | null;
  webhook_url: string | null;
  telegram_chat_id: string | null;
  alert_type: AlertType;
  threshold: number | null;
}

export interface TelegramStatus {
  configured: boolean;
  bot_username: string | null;
}

export interface TelegramPairingResponse {
  token: string;
  deep_link: string;
}

export interface TelegramPairingStatus {
  paired: boolean;
  exists: boolean;
  chat_id: string | null;
  display_name: string | null;
}

export type EventKind =
  | 'tick_start'
  | 'tick_result'
  | 'alert'
  | 'tick_done'
  | 'job_stop'
  | 'error';

export interface TickEvent {
  id: number;
  ts: string;
  job_id: string;
  job_kind: JobKind;
  platform: string;
  kind: EventKind;
  message: string;
}
