import { Fragment } from 'react';
import { motion } from 'framer-motion';
import { usePlatforms } from '~/hooks/usePlatforms';
import type { JobKind } from '~/types/job';

interface Props {
  view: JobKind;
}

/**
 * Inline strip listing supported platforms above the watch form.
 * Source of truth is /api/platforms (i.e. the SCRAPERS dict).
 */
export function SupportedPlatforms({ view }: Props) {
  const platforms = usePlatforms();
  if (!platforms) return <Skeleton />;

  const list = platforms[view];
  if (list.length === 0) {
    return (
      <div className="chrome-label text-mute mb-3">
        no platforms registered for {view}s
      </div>
    );
  }

  return (
    <motion.div
      key={view}
      initial={{ opacity: 0, y: -2 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-baseline flex-wrap gap-x-1 mb-3"
    >
      <span className="chrome-label mr-3">supported</span>
      {list.map((p, i) => (
        <Fragment key={p}>
          {i > 0 && (
            <span className="text-mute select-none mx-2 tabular text-[12px]">/</span>
          )}
          <span className="font-mono text-[12.5px] text-fg lowercase">{p}</span>
        </Fragment>
      ))}
    </motion.div>
  );
}

function Skeleton() {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      <span className="chrome-label">supported</span>
      <span className="chrome-label text-mute opacity-60">loading…</span>
    </div>
  );
}
