import { motion } from 'framer-motion';
import { Section } from '~/components/Section';
import { SupportedPlatforms } from '~/components/SupportedPlatforms';
import { WatchForm } from '~/components/WatchForm';
import { WatchList } from '~/components/WatchList';
import { Terminal } from '~/components/Terminal';
import { useJobs } from '~/hooks/useJobs';
import type { View } from '~/components/Tabs';
import type { JobKind } from '~/types/job';

interface ConsoleProps {
  view: View;
}

export function Console({ view }: ConsoleProps) {
  const kind: JobKind = view === 'hotels' ? 'hotel' : 'product';
  const { jobs, loading, error, create, stop } = useJobs(kind);

  const newWatchHint = view === 'hotels'
    ? 'track a hotel URL · re-scrapes the date in your URL'
    : 'track a product URL';

  const runningCount = jobs.filter((j) => j.status === 'running' || j.status === 'pending').length;
  const watchesHint = jobs.length === 0
    ? 'nothing watched yet'
    : `${jobs.length} active · ${runningCount} running`;

  return (
    <motion.div
      key={view}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col gap-12"
    >
      <Section index="01" label="New watch" hint={newWatchHint}>
        <SupportedPlatforms view={kind} />
        <WatchForm view={kind} onSubmit={async (p) => { await create(p); }} />
      </Section>

      <Section index="02" label="Active watches" hint={watchesHint}>
        <WatchList jobs={jobs} loading={loading} error={error} onStop={stop} />
      </Section>

      <Section index="03" label="Tick log" hint="live · server-sent events">
        <Terminal view={kind} />
      </Section>
    </motion.div>
  );
}
