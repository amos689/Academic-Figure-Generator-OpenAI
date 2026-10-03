import { useEffect, useState } from 'react';

export function useObjectUrl(blob?: Blob) {
  const [resource, setResource] = useState<{ blob: Blob; url: string }>();
  useEffect(() => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    // Object URLs are external resources; expose only after creation and revoke on cleanup.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResource({ blob, url });
    return () => URL.revokeObjectURL(url);
  }, [blob]);
  return resource?.blob === blob ? resource?.url ?? '' : '';
}
