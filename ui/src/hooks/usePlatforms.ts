import { useEffect, useState } from 'react';
import { api } from '~/lib/api';

interface Platforms {
  product: string[];
  hotel: string[];
}

/**
 * Fetches the supported-platforms list once. The data is small and
 * rarely changes, so plain useEffect + useState is enough — no React
 * Query needed.
 */
export function usePlatforms(): Platforms | null {
  const [data, setData] = useState<Platforms | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .platforms()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData({ product: [], hotel: [] });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return data;
}
