/** Compact relative-time formatter — "12s ago", "3m ago", "14:02". */
export function relativeTime(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return '—';
  const then = new Date(iso);
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
