import { motion } from 'framer-motion';
import type { View } from './Tabs';

interface Row {
  id: string;
  state: 'running' | 'idle' | 'alerted';
  platform: string;
  price: string;
  status: string;
  age: string;
}

const productRows: Row[] = [
  { id: '1', state: 'running', platform: 'amazon',   price: '₹156.00',  status: 'in stock',     age: '12s ago' },
  { id: '2', state: 'idle',    platform: 'flipkart', price: '₹699',     status: 'in stock',     age: '2m ago'  },
  { id: '3', state: 'alerted', platform: 'amazfit',  price: '₹7,499',   status: 'alerted',      age: '14:02'   },
  { id: '4', state: 'idle',    platform: 'myntra',   price: '₹2,999',   status: 'out of stock', age: '5m ago'  },
];

const hotelRows: Row[] = [
  { id: 'h1', state: 'running', platform: 'booking',    price: '₹4,820',  status: 'best in window', age: '1m ago'  },
  { id: 'h2', state: 'idle',    platform: 'makemytrip', price: '₹5,140',  status: 'best in window', age: '3m ago'  },
  { id: 'h3', state: 'alerted', platform: 'agoda',      price: '₹3,990',  status: 'alerted',        age: '13:48'   },
];

interface Props {
  view: View;
}

export function WatchListStub({ view }: Props) {
  const rows = view === 'hotels' ? hotelRows : productRows;
  return (
    <div className="bg-surface hairline" style={{ borderColor: 'var(--color-rule)' }}>
      {rows.map((row, i) => (
        <RowView key={row.id} row={row} index={i} isLast={i === rows.length - 1} />
      ))}
    </div>
  );
}

function RowView({ row, index, isLast }: { row: Row; index: number; isLast: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -2 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className={`
        grid grid-cols-[28px_120px_1fr_140px_100px_72px] items-center gap-4
        px-4 py-3 text-[13px] text-fg
        hover:bg-elevated transition-colors group
        ${isLast ? '' : 'hairline-b'}
      `}
    >
      <StatusDot state={row.state} />
      <span className="font-mono text-dim lowercase">{row.platform}</span>
      <span className="tabular text-fg">{row.price}</span>
      <span className={statusClass(row.state)}>{row.status}</span>
      <span className="tabular text-mute">{row.age}</span>
      <RowAction state={row.state} />
    </motion.div>
  );
}

function statusClass(state: Row['state']): string {
  if (state === 'alerted') return 'text-alert';
  if (state === 'running') return 'text-ok';
  return 'text-dim';
}

function StatusDot({ state }: { state: Row['state'] }) {
  if (state === 'alerted') {
    return <span className="text-alert tabular text-[14px]">✓</span>;
  }
  if (state === 'running') {
    return (
      <motion.span
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        className="inline-block w-1.5 h-1.5 bg-ok"
      />
    );
  }
  return <span className="inline-block w-1.5 h-1.5 border border-dim" />;
}

function RowAction({ state }: { state: Row['state'] }) {
  const label = state === 'alerted' ? 'HIDE' : 'STOP';
  return (
    <button
      type="button"
      className="
        chrome-label tabular tracking-[0.18em]
        text-mute hover:text-err
        transition-colors text-right
      "
    >
      [{label}]
    </button>
  );
}
