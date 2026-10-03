import { useCallback, useEffect, useRef, useState } from 'react';
import { getApiErrorMessage } from '../lib/apiError';

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, fallback: string, pollMs = 0) {
  const [result, setResult] = useState<{ owner: typeof load; data: T }>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const request = useRef(0);
  const refresh = useCallback(async () => {
    const version = ++request.current;
    controller.current?.abort();
    const next = new AbortController();
    controller.current = next;
    setRefreshing(true);
    try {
      const result = await load(next.signal);
      if (next.signal.aborted || version !== request.current) return;
      setResult({ owner: load, data: result });
      setError('');
    } catch (cause) {
      if (!next.signal.aborted && version === request.current) setError(getApiErrorMessage(cause, fallback));
    } finally {
      if (!next.signal.aborted && version === request.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [load, fallback]);
  useEffect(() => {
    let mounted = true;
    queueMicrotask(() => { if (mounted) void refresh(); });
    return () => { mounted = false; controller.current?.abort(); };
  }, [refresh]);
  useEffect(() => {
    if (!pollMs || refreshing) return;
    const timer = setTimeout(() => { void refresh(); }, pollMs);
    return () => clearTimeout(timer);
  }, [pollMs, refresh, refreshing]);
  return { data: result?.owner === load ? result.data : undefined, error, loading, refreshing, refresh };
}
