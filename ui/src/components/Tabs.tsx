import { motion } from 'framer-motion';

export type View = 'products' | 'hotels';

interface TabsProps {
  value: View;
  onChange: (next: View) => void;
}

const TABS: { id: View; label: string }[] = [
  { id: 'products', label: 'products' },
  { id: 'hotels',   label: 'hotels'   },
];

/**
 * Segmented control. Animated underline uses Framer's layoutId so the
 * bar slides between tabs instead of snapping — that motion is the only
 * feedback an operator gets, so it has to be precise.
 */
export function Tabs({ value, onChange }: TabsProps) {
  return (
    <div className="hairline flex bg-surface">
      {TABS.map((tab) => {
        const active = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`
              relative px-4 h-8 chrome-label tabular tracking-[0.18em]
              transition-colors
              ${active ? 'text-fg' : 'text-mute hover:text-dim'}
            `}
          >
            {tab.label}
            {active && (
              <motion.span
                layoutId="tab-indicator"
                className="absolute inset-x-0 bottom-0 h-px bg-ok"
                transition={{ type: 'spring', stiffness: 500, damping: 40 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
