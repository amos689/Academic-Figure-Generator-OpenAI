import { useCallback, useRef, useState } from 'react';
import { workbenchApi } from '../lib/api';
import { activeStatus } from '../lib/workbench';
import { useI18n } from '../lib/i18n';
import { useResource } from './useResource';
import type { DocumentItem, FigureExport, FigureImage, Job, Project, Prompt } from '../lib/types';

interface WorkspaceData {
  project: Project;
  documents: DocumentItem[];
  prompts: Prompt[];
  images: FigureImage[];
  jobs: Job[];
  exports: FigureExport[];
  unavailable: string[];
}

export function useWorkspace(id: string) {
  const { t } = useI18n();
  const [pollMs, setPollMs] = useState(0);
  const previous = useRef<WorkspaceData | undefined>(undefined);
  const load = useCallback(async (signal: AbortSignal): Promise<WorkspaceData> => {
    const project = await workbenchApi.project(id, signal);
    const results = await Promise.allSettled([
      workbenchApi.documents(id, signal), workbenchApi.prompts(id, signal),
      workbenchApi.images(id, signal), workbenchApi.jobs(id, signal), workbenchApi.exports(id, signal),
    ] as const);
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    const [docs, prompts, images, jobs, exports] = results;
    const data = {
      project,
      documents: docs.status === 'fulfilled' ? docs.value : previous.current?.documents ?? [],
      prompts: prompts.status === 'fulfilled' ? prompts.value : previous.current?.prompts ?? [],
      images: images.status === 'fulfilled' ? images.value : previous.current?.images ?? [],
      jobs: jobs.status === 'fulfilled' ? jobs.value : previous.current?.jobs ?? [],
      exports: exports.status === 'fulfilled' ? exports.value : previous.current?.exports ?? [],
      unavailable: results.flatMap((result, index) => result.status === 'rejected' ? [['documents', 'prompts', 'images', 'jobs', 'exports'][index]] : []),
    };
    const active = data.jobs.some(job => activeStatus(job.status)) || data.documents.some(doc => activeStatus(doc.parse_status)) || data.images.some(image => activeStatus(image.generation_status));
    setPollMs(active || data.unavailable.length ? 5000 : 0);
    previous.current = data;
    return data;
  }, [id]);
  return useResource(load, t('Workspace could not be loaded.', '无法加载工作区。'), pollMs);
}
