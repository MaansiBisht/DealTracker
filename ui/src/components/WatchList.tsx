import { motion, AnimatePresence } from 'framer-motion';
import { relativeTime } from '~/lib/time';
import type { Job, JobStatus } from '~/types/job';

interface Props {
  jobs: Job[];
  loading: boolean;
  error: string | null;
  onStop: (id: string) => Promise<void>;
}

export function WatchList({ jobs, loading, error, onStop }: Props) {
  if (loading && jobs.length === 0) {
    return <Placeholder text="loading watches…" />;
  }
  if (error) {
    return <Placeholder text={`error · ${error}`} variant="error" />;
  }
  if (jobs.length === 0) {
    return <Placeholder text="no active watches · submit a URL above" />;
  }

  return (
    <div className="bg-surface hairline" style={{ borderColor: 'var(--color-rule)' }}>
      <AnimatePresence initial={false}>
        {jobs.map((job, i) => (
          <Row key={job.id} job={job} isLast={i === jobs.length - 1} onStop={onStop} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function Row({ job, isLast, onStop }: { job: Job; isLast: boolean; onStop: (id: string) => Promise<void> }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -2 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, height: 0, marginTop: 0, marginBottom: 0, paddingTop: 0, paddingBottom: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className={`
        grid grid-cols-[28px_120px_1fr_160px_100px_72px] items-center gap-4
        px-4 py-3 text-[13px] text-fg
        hover:bg-elevated transition-colors group
        ${isLast ? '' : 'hairline-b'}
      `}
    >
      <StatusDot status={job.status} />
      <span className="font-mono text-dim lowercase truncate">{job.platform}</span>
      <PriceCell job={job} />
      <span className={statusClass(job.status)}>{statusLabel(job)}</span>
      <span className="tabular text-mute">
        {relativeTime(job.last_checked_at ?? job.created_at)}
      </span>
      <button
        type="button"
        onClick={() => onStop(job.id)}
        className="chrome-label tabular tracking-[0.18em] text-mute hover:text-err transition-colors text-right"
      >
        [STOP]
      </button>
    </motion.div>
  );
}

function PriceCell({ job }: { job: Job }) {
  if (job.last_price) {
    return <span className="tabular text-fg truncate">{formatPrice(job.last_price)}</span>;
  }
  if (job.threshold != null) {
    return (
      <span className="tabular text-mute truncate">
        target ≤ ₹{job.threshold.toLocaleString('en-IN')}
      </span>
    );
  }
  return <span className="tabular text-mute">—</span>;
}

function formatPrice(raw: string): string {
  if (raw.includes('₹') || raw.includes('$') || raw.includes('€')) return raw;
  const n = parseFloat(raw);
  if (!Number.isFinite(n)) return raw;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function statusLabel(job: Job): string {
  if (job.status === 'alerted') return 'alerted';
  if (job.status === 'pending') return 'queued';
  if (job.status === 'running') return job.last_status ?? 'running';
  if (job.status === 'idle')    return job.last_status ?? 'idle';
  if (job.status === 'error')   return 'error';
  if (job.status === 'stopped') return 'stopped';
  return job.status;
}

function statusClass(status: JobStatus): string {
  if (status === 'alerted') return 'text-alert';
  if (status === 'running') return 'text-ok';
  if (status === 'error')   return 'text-err';
  return 'text-dim';
}

function StatusDot({ status }: { status: JobStatus }) {
  if (status === 'alerted') {
    return <span className="text-alert tabular text-[14px]">✓</span>;
  }
  if (status === 'running' || status === 'pending') {
    return (
      <motion.span
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        className="inline-block w-1.5 h-1.5 bg-ok"
      />
    );
  }
  if (status === 'error') {
    return <span className="inline-block w-1.5 h-1.5 bg-err" />;
  }
  return <span className="inline-block w-1.5 h-1.5 border border-dim" />;
}

function Placeholder({ text, variant = 'idle' }: { text: string; variant?: 'idle' | 'error' }) {
  return (
    <div
      className={`bg-surface hairline px-4 py-6 text-center chrome-label tabular ${
        variant === 'error' ? 'text-err' : 'text-mute'
      }`}
    >
      {text}
    </div>
  );
}
