import type {
  Job,
  JobCreatePayload,
  JobKind,
  TelegramPairingResponse,
  TelegramPairingStatus,
  TelegramStatus,
  TickEvent,
} from '~/types/job';

/**
 * Typed fetch wrapper. All endpoints are relative — Vite proxies /api in
 * dev (see vite.config.ts), and FastAPI serves them same-origin in prod.
 */

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function http<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    let body: unknown;
    try { body = await res.json(); } catch { body = await res.text().catch(() => null); }
    const detail =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => http<{ status: 'ok'; version: string }>('/api/health'),

  platforms: () => http<{ product: string[]; hotel: string[] }>('/api/platforms'),

  listJobs: (kind?: JobKind) => {
    const qs = kind ? `?kind=${kind}` : '';
    return http<Job[]>(`/api/jobs${qs}`);
  },

  createJob: (payload: JobCreatePayload) =>
    http<Job>('/api/jobs', { method: 'POST', body: JSON.stringify(payload) }),

  stopJob: (id: string) =>
    http<Job>(`/api/jobs/${encodeURIComponent(id)}/stop`, { method: 'POST' }),

  telegramStatus: () => http<TelegramStatus>('/api/telegram/status'),

  telegramStartPairing: () =>
    http<TelegramPairingResponse>('/api/telegram/start-pairing', { method: 'POST' }),

  telegramPairingStatus: (token: string) =>
    http<TelegramPairingStatus>(`/api/telegram/pairing/${encodeURIComponent(token)}`),

  recentEvents: (opts?: { limit?: number; jobId?: string; kind?: JobKind }) => {
    const params = new URLSearchParams();
    if (opts?.limit) params.set('limit', String(opts.limit));
    if (opts?.jobId) params.set('job_id', opts.jobId);
    if (opts?.kind) params.set('kind', opts.kind);
    const qs = params.toString();
    return http<TickEvent[]>(`/api/events/recent${qs ? `?${qs}` : ''}`);
  },
};

export { ApiError };
