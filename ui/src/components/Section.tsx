import type { ReactNode } from 'react';

interface SectionProps {
  index: string;
  label: string;
  hint?: string;
  children: ReactNode;
  action?: ReactNode;
}

/**
 * Numbered editorial heading + content surface.
 * The number is not decoration — operators can say "look at section 02".
 */
export function Section({ index, label, hint, children, action }: SectionProps) {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between hairline-b pb-2 gap-3">
        <div className="flex items-baseline flex-wrap gap-x-3 sm:gap-x-4 gap-y-1 min-w-0">
          <span className="text-mute tabular text-[11px] tracking-[0.2em]">
            {index}
          </span>
          <h2 className="font-sans text-fg text-[15px] font-medium tracking-[-0.01em]">
            {label}
          </h2>
          {hint && (
            <span className="chrome-label whitespace-normal">— {hint}</span>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </header>
      <div>{children}</div>
    </section>
  );
}
