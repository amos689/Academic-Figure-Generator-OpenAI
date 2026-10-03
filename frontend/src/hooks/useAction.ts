import { useEffect, useRef, useState } from 'react';
import { getApiErrorMessage, isUnknownOutcome } from '../lib/apiError';
import { useI18n } from '../lib/i18n';

export function useAction() {
  const { t } = useI18n();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [unknown, setUnknown] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function run<T>(action: () => Promise<T>, billed = false): Promise<T | undefined> {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError('');
    setUnknown(false);
    try {
      return await action();
    } catch (cause) {
      if (mounted.current) {
        setError(getApiErrorMessage(cause, t('Request failed. Check the connection and refresh.', '请求失败，请检查连接并刷新。')));
        setUnknown(billed && isUnknownOutcome(cause));
      }
    } finally {
      busy.current = false;
      if (mounted.current) setPending(false);
    }
  }
  return { run, pending, error, unknown, setError };
}
