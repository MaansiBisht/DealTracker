import { useEffect, useRef, useState } from 'react';
import { api } from '~/lib/api';
import type { JobKind, TickEvent } from '~/types/job';

interface Options {
  kind?: JobKind;
  cap?: number;
  replay?: number;
}

interface Result {
  events: TickEvent[];
  connected: boolean;
}

/**
 * Manages SSE connection plus initial replay.
 *
 * Lifecycle per `kind`:
 *   1. fetch /api/events/recent?kind=… (replay up to `replay` rows)
 *   2. open EventSource at /api/events/stream
 *   3. drop SSE events that don't match the requested kind
 *   4. close + restart when `kind` changes
 */
export function useEventStream({ kind, cap = 500, replay = 100 }: Options = {}): Result {
  const [events, setEvents] = useState<TickEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seenIds = useRef<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    seenIds.current = new Set();
    setEvents([]);
    setConnected(false);

    api
      .recentEvents({ limit: replay, kind })
      .then((rows) => {
        if (cancelled) return;
        const fresh = rows.filter((r) => !seenIds.current.has(r.id));
        fresh.forEach((r) => seenIds.current.add(r.id));
        setEvents((prev) => mergeAndCap(prev, fresh, cap));
      })
      .catch(() => {
        // Replay failure is non-fatal — live stream may still work.
      });

    const es = new EventSource('/api/events/stream');
    es.addEventListener('tick', (raw) => {
      try {
        const ev = JSON.parse((raw as MessageEvent).data) as TickEvent;
        if (kind && ev.job_kind !== kind) return;
        if (seenIds.current.has(ev.id)) return;
        seenIds.current.add(ev.id);
        setEvents((prev) => mergeAndCap(prev, [ev], cap));
      } catch {
        // ignore bad message
      }
    });
    es.onopen = () => !cancelled && setConnected(true);
    es.onerror = () => !cancelled && setConnected(false);

    return () => {
      cancelled = true;
      es.close();
    };
  }, [kind, cap, replay]);

  return { events, connected };
}

function mergeAndCap(prev: TickEvent[], extra: TickEvent[], cap: number): TickEvent[] {
  const next = prev.concat(extra);
  return next.length > cap ? next.slice(next.length - cap) : next;
}
