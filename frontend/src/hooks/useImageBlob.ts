import { useCallback } from 'react';
import { fetchAuthedBlob } from '../lib/blob';
import { useI18n } from '../lib/i18n';
import { useResource } from './useResource';
import { useObjectUrl } from './useObjectUrl';

export function useImageBlob(id: string) {
  const { t } = useI18n();
  const load = useCallback((signal: AbortSignal) => fetchAuthedBlob(`/images/${encodeURIComponent(id)}/download`, signal), [id]);
  const resource = useResource(load, t('Preview could not be loaded.', '无法加载预览。'));
  const url = useObjectUrl(resource.data?.blob);
  return { ...resource, url };
}
