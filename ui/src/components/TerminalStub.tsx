import { motion } from 'framer-motion';
import type { View } from './Tabs';

type LineKind = 'tick_start' | 'tick_result' | 'alert' | 'tick_done' | 'job_stop';

interface Line {
  ts: string;
  job: string;
  kind: LineKind;
  text: string;
}

const productLog: Line[] = [
  { ts: '14:02:11', job: 'amazon  ', kind: 'tick_start',  text: 'tick start' },
  { ts: '14:02:13', job: 'amazon  ', kind: 'tick_result', text: 'price=₹156.00 stock=in_stock' },
  { ts: '14:02:13', job: 'amazon  ', kind: 'alert',       text: 'threshold ₹200 → ALERT EMAIL SENT' },
  { ts: '14:02:13', job: 'amazon  ', kind: 'tick_done',   text: 'tick done. job=ALERTED' },
  { ts: '14:02:30', job: 'flipkart', kind: 'tick_start',  text: 'tick start' },
  { ts: '14:02:32', job: 'flipkart', kind: 'tick_result', text: 'price=699 stock=in_stock' },
  { ts: '14:02:32', job: 'flipkart', kind: 'tick_done',   text: 'threshold 500 not met. next=15:02' },
  { ts: '14:03:00', job: 'amazfit ', kind: 'tick_start',  text: 'tick start' },
  { ts: '14:03:02', job: 'amazfit ', kind: 'tick_result', text: 'price=7499 stock=out_of_stock' },
  { ts: '14:03:02', job: 'amazfit ', kind: 'tick_done',   text: 'no change. next=15:03' },
];

const hotelLog: Line[] = [
  { ts: '13:48:01', job: 'booking ', kind: 'tick_start',  text: 'tick start · scanning 30 days' },
  { ts: '13:48:42', job: 'booking ', kind: 'tick_result', text: 'best=₹4,820 on 2026-05-24 (Sun)' },
  { ts: '13:48:42', job: 'booking ', kind: 'tick_done',   text: 'threshold 4500 not met. next=16:48' },
  { ts: '13:49:00', job: 'agoda   ', kind: 'tick_start',  text: 'tick start · scanning 30 days' },
  { ts: '13:49:38', job: 'agoda   ', kind: 'tick_result', text: 'best=₹3,990 on 2026-05-19 (Tue)' },
  { ts: '13:49:38', job: 'agoda   ', kind: 'alert',       text: 'threshold 4000 met → ALERT EMAIL SENT' },
  { ts: '13:49:38', job: 'agoda   ', kind: 'tick_done',   text: 'tick done. job=ALERTED' },
  { ts: '13:50:11', job: 'mmt     ', kind: 'tick_start',  text: 'tick start · scanning 30 days' },
  { ts: '13:50:55', job: 'mmt     ', kind: 'tick_result', text: 'best=₹5,140 on 2026-06-02 (Tue)' },
  { ts: '13:50:55', job: 'mmt     ', kind: 'tick_done',   text: 'threshold 4800 not met. next=16:50' },
];

interface Props {
  view: View;
}

export function TerminalStub({ view }: Props) {
  const log = view === 'hotels' ? hotelLog : productLog;
  return (
    <div className="bg-terminal hairline" style={{ borderColor: 'var(--color-rule)' }}>
      <TerminalHeader />
      <div className="px-4 py-3 max-h-[420px] overflow-y-auto font-mono text-[12.5px] leading-[1.7]">
        {log.map((line, i) => (
          <LineView key={`${view}-${i}`} line={line} index={i} />
        ))}
        <Cursor />
      </div>
    </div>
  );
}

function TerminalHeader() {
  return (
    <div className="hairline-b px-4 h-9 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="inline-block w-1.5 h-1.5 bg-ok" />
        <span className="chrome-label">stream live</span>
      </div>
      <button
        type="button"
        className="chrome-label tabular tracking-[0.18em] text-mute hover:text-fg transition-colors"
      >
        [ ⏸  PAUSE ]
      </button>
    </div>
  );
}

function LineView({ line, index }: { line: Line; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.02, duration: 0.18 }}
      className="grid grid-cols-[80px_120px_1fr] gap-4 tabular"
    >
      <span className="text-mute">{line.ts}</span>
      <span className="text-dim">[{line.job}]</span>
      <span className={textClass(line.kind)}>{line.text}</span>
    </motion.div>
  );
}

function textClass(kind: LineKind): string {
  if (kind === 'alert') return 'text-alert';
  if (kind === 'tick_start') return 'text-info';
  if (kind === 'tick_result') return 'text-fg';
  if (kind === 'tick_done') return 'text-dim';
  return 'text-fg';
}

function Cursor() {
  return (
    <motion.span
      animate={{ opacity: [1, 1, 0, 0] }}
      transition={{ duration: 0.8, repeat: Infinity, ease: 'linear', times: [0, 0.5, 0.5, 1] }}
      className="inline-block w-[8px] h-[14px] bg-ok translate-y-[2px] ml-[200px]"
    />
  );
}
