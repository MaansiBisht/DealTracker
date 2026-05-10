import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '~/lib/api';
import type { Job, JobCreatePayload, JobKind } from '~/types/job';

interface UseJobsResult {
  jobs: Job[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  create: (payload: JobCreatePayload) => Promise<Job>;
  stop: (id: string) => Promise<void>;
}

/**
 * Polling-based job list. Step 5 swaps the polling for SSE-driven
 * invalidation — same shape, less network chatter.
 */
export function useJobs(kind: JobKind, pollMs = 4000): UseJobsResult {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listJobs(kind);
      if (!cancelled.current) {
        setJobs(list);
        setError(null);
      }
    } catch (e) {
      if (!cancelled.current) {
        setError(e instanceof ApiError ? e.message : 'failed to load jobs');
      }
    } finally {
      if (!cancelled.current) setLoading(false);
    }
  }, [kind]);

  useEffect(() => {
    cancelled.current = false;
    setLoading(true);
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => {
      cancelled.current = true;
      clearInterval(id);
    };
  }, [refresh, pollMs]);

  const create = useCallback(async (payload: JobCreatePayload) => {
    const created = await api.createJob(payload);
    setJobs((prev) => [created, ...prev]);
    return created;
  }, []);

  const stop = useCallback(async (id: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
    try {
      await api.stopJob(id);
    } catch (e) {
      await refresh();
      throw e;
    }
  }, [refresh]);

  return { jobs, loading, error, refresh, create, stop };
}
