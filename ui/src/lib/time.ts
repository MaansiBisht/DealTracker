/**
 * Parse an ISO string from the API.
 *
 * SQLite-backed SQLAlchemy returns naive datetimes despite the column
 * being timezone-aware, so the API often emits "2026-05-10T12:48:47"
 * with no TZ marker. Plain `new Date(...)` would then interpret it as
 * local time, throwing off ages by the browser's UTC offset. We append
 * 'Z' when no marker is present so server timestamps are read as UTC.
 */
export function parseServerTime(iso: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + 'Z');
}

/** Compact relative-time formatter — "12s ago", "3m ago", "14:02". */
export function relativeTime(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return '—';
  const then = parseServerTime(iso);
  const diffMs = now.getTime() - then.getTime();
  if (diffMs < 0) return 'now';
  const sec = Math.floor(diffMs / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 12) return `${hr}h ago`;
  return then.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

/** HH:MM:SS in the viewer's local timezone — used by the terminal pane. */
export function formatLocalTime(iso: string): string {
  const d = parseServerTime(iso);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}
