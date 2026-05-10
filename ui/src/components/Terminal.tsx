import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useEventStream } from '~/hooks/useEventStream';
import { formatLocalTime } from '~/lib/time';
import type { EventKind, JobKind, TickEvent } from '~/types/job';

interface Props {
  view: JobKind;
}

/**
 * Live tick log. Streams via SSE, replays the last 100 events on mount,
 * caps at 500 lines in memory. Auto-scrolls to bottom unless the user
 * has scrolled up — then it pauses until they hit the resume button.
 */
export function Terminal({ view }: Props) {
  const { events, connected } = useEventStream({ kind: view });
  const scrollRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);

  useLayoutEffect(() => {
    if (paused) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [events, paused]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    function onScroll() {
      if (!el) return;
      const fromBottom = el.scrollHeight - el.clientHeight - el.scrollTop;
      if (fromBottom > 12) setPaused(true);
      else setPaused(false);
    }
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  function resume() {
    const el = scrollRef.current;
    if (!el) return;
    setPaused(false);
    el.scrollTop = el.scrollHeight;
  }

  return (
    <div className="bg-terminal hairline" style={{ borderColor: 'var(--color-rule)' }}>
      <Header connected={connected} count={events.length} paused={paused} onResume={resume} />
      <div
        ref={scrollRef}
        className="
          px-4 py-3 max-h-[420px]
          overflow-y-auto overflow-x-auto
          font-mono text-[11.5px] sm:text-[12.5px] leading-[1.7]
        "
      >
        {events.length === 0 ? (
          <Empty connected={connected} />
        ) : (
          events.map((line) => <Line key={line.id} line={line} />)
        )}
        {!paused && <Cursor />}
      </div>
    </div>
  );
}

function Header({
  connected,
  count,
  paused,
  onResume,
}: {
  connected: boolean;
  count: number;
  paused: boolean;
  onResume: () => void;
}) {
  return (
    <div className="hairline-b px-4 h-9 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <ConnectionDot connected={connected} />
        <span className="chrome-label">
          {connected ? 'stream live' : 'reconnecting…'}
        </span>
        <span className="chrome-label text-mute tabular">· {count} lines</span>
      </div>
      {paused && (
        <button
          type="button"
          onClick={onResume}
          className="chrome-label tabular tracking-[0.18em] text-alert hover:text-fg transition-colors"
        >
          [ ▶  RESUME ]
        </button>
      )}
    </div>
  );
}

function ConnectionDot({ connected }: { connected: boolean }) {
  if (connected) {
    return (
      <motion.span
        animate={{ opacity: [1, 0.5, 1] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
        className="inline-block w-1.5 h-1.5 bg-ok"
      />
    );
  }
  return <span className="inline-block w-1.5 h-1.5 bg-alert" />;
}

function Line({ line }: { line: TickEvent }) {
  const tone = textClass(line.kind);
  const flash = line.kind === 'alert';
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={
        flash
          ? { opacity: 1, backgroundColor: ['rgba(255,180,80,0.18)', 'rgba(255,180,80,0)'] }
          : { opacity: 1 }
      }
      transition={{ duration: flash ? 0.7 : 0.18, ease: 'easeOut' }}
      className="
        grid grid-cols-[68px_92px_max-content] sm:grid-cols-[80px_120px_1fr]
        gap-3 sm:gap-4 tabular px-1 -mx-1
        whitespace-nowrap sm:whitespace-normal
      "
    >
      <span className="text-mute">{formatLocalTime(line.ts)}</span>
      <span className="text-dim">[{padPlatform(line.platform)}]</span>
      <span className={tone}>{line.message}</span>
    </motion.div>
  );
}

function Empty({ connected }: { connected: boolean }) {
  return (
    <div className="text-mute chrome-label tabular py-6 text-center">
      {connected ? 'waiting for tick events …' : 'no events yet · connecting'}
    </div>
  );
}

function Cursor() {
  return (
    <motion.span
      animate={{ opacity: [1, 1, 0, 0] }}
      transition={{ duration: 0.8, repeat: Infinity, ease: 'linear', times: [0, 0.5, 0.5, 1] }}
      className="inline-block w-[8px] h-[14px] bg-ok translate-y-[2px] ml-[160px] sm:ml-[200px]"
    />
  );
}

function textClass(kind: EventKind): string {
  if (kind === 'alert') return 'text-alert';
  if (kind === 'error') return 'text-err';
  if (kind === 'tick_start') return 'text-info';
  if (kind === 'tick_done' || kind === 'job_stop') return 'text-dim';
  return 'text-fg';
}

function padPlatform(p: string): string {
  return p.padEnd(8, ' ').slice(0, 8);
}
