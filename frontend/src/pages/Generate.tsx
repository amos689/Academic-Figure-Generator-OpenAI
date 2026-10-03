import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Sparkles } from 'lucide-react';
import { workbenchApi } from '../lib/api';
import { DEFAULT_SETTINGS, activeStatus, newRequestKey, withPalette } from '../lib/workbench';
import type { FigureImage, Job } from '../lib/types';
import { useI18n } from '../lib/i18n';
import { useAction } from '../hooks/useAction';
import { useResource } from '../hooks/useResource';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ErrorNotice, Field, IconButton, Loading } from '../components/workbench/Common';
import { GenerationControls } from '../components/workbench/GenerationControls';
import { ImageHistory } from '../components/workbench/ImageHistory';
import { JobsPanel } from '../components/workbench/JobsPanel';

const savedProject = () => { try { return localStorage.getItem('workbench.directProject') || ''; } catch { return ''; } };

export function Generate() {
  const { t } = useI18n();
  const [prompt, setPrompt] = useState('');
  const [projectId, setProjectId] = useState(savedProject);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [settingsProject, setSettingsProject] = useState('');
  const [receipt, setReceipt] = useState('');
  const [poll, setPoll] = useState(0);
  const action = useAction();
  const projects = useResource(workbenchApi.projects, t('Could not load projects.', '无法加载项目。'));
  const palettes = useResource(workbenchApi.palettes, t('Could not load palettes.', '无法加载配色。'));
  const config = useResource(workbenchApi.configuration, t('Could not load effective settings.', '无法加载有效配置。'));
  const load = useCallback(async (signal: AbortSignal): Promise<{ images: FigureImage[]; jobs: Job[] }> => {
    if (!projectId) return { images: [], jobs: (await workbenchApi.jobs(undefined, signal)).filter(job => job.kind === 'image') };
    const [images, jobs] = await Promise.all([workbenchApi.images(projectId, signal), workbenchApi.jobs(projectId, signal)]);
    if (!signal.aborted) setPoll(images.some(image => activeStatus(image.generation_status)) || jobs.some(job => activeStatus(job.status)) ? 5000 : 0);
    return { images, jobs };
  }, [projectId]);
  const history = useResource(load, t('Could not load history.', '无法加载历史记录。'), poll);
  const loadReceipt = useCallback(async (signal: AbortSignal) => {
    if (!receipt) return null;
    const image = await workbenchApi.image(receipt, signal);
    if (!signal.aborted && image.project_id) { setProjectId(image.project_id); setReceipt(''); }
    return image;
  }, [receipt]);
  const accepted = useResource(loadReceipt, t('Request accepted; image details are temporarily unavailable.', '请求已接受，图像详情暂时不可用。'));
  const selectedProject = projects.data?.items.find(project => project.id === projectId);
  if (selectedProject && settingsProject !== projectId) {
    setSettingsProject(projectId);
    setSettings(previous => ({ ...previous, color_scheme: selectedProject.color_scheme, custom_colors: selectedProject.custom_colors ?? undefined, style_preset: selectedProject.style_preset ?? 'classic' }));
  }
  useEffect(() => { try { localStorage.setItem('workbench.directProject', projectId); } catch { /* Session-only preference. */ } }, [projectId]);

  return <div className="space-y-5"><header className="flex items-center justify-between gap-3 border-b pb-4"><h1 className="text-xl font-semibold">{t('Direct generation', '直接生成')}</h1><IconButton label={t('Refresh history', '刷新历史')} disabled={history.refreshing} onClick={() => { void history.refresh(); void accepted.refresh(); void projects.refresh(); }}><RefreshCw className={`h-4 w-4 ${history.refreshing ? 'animate-spin' : ''}`} /></IconButton></header>
    <ErrorNotice message={projects.error || palettes.error || config.error || history.error || accepted.error} />
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]"><form className="min-w-0 space-y-4 xl:border-r xl:pr-5" onSubmit={e => {
      e.preventDefault();
      void action.run(async () => {
        const response = await workbenchApi.directImage({ ...withPalette(settings, palettes.data ?? []), prompt: prompt.trim(), ...(projectId ? { project_id: projectId } : {}), idempotency_key: newRequestKey() });
        setReceipt(response.id);
        await history.refresh();
      }, true);
    }}>
      <Field label={t('Project', '项目')}><select value={projectId} disabled={action.pending} onChange={e => {
        setReceipt(''); setProjectId(e.target.value);
        const project = projects.data?.items.find(p => p.id === e.target.value);
        if (project) setSettings(previous => ({ ...previous, color_scheme: project.color_scheme, custom_colors: project.custom_colors ?? undefined, style_preset: project.style_preset ?? 'classic' }));
      }}><option value="">{t('Default direct-generation project', '默认直接生成项目')}</option>{projectId && !projects.data?.items.some(p => p.id === projectId) && <option value={projectId}>{projectId}</option>}{projects.data?.items.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
      <Field label={t('Prompt', '提示词')}><Textarea rows={12} value={prompt} onChange={e => setPrompt(e.target.value)} maxLength={60000} required disabled={action.pending} /></Field>
      <GenerationControls value={settings} onChange={setSettings} palettes={palettes.data ?? []} disabled={action.pending} />
      <ErrorNotice message={action.error} unknown={action.unknown} />
      {!!receipt && <p role="status" className="break-all text-xs text-muted-foreground">{t('Accepted image', '已接受图像')}: {receipt}</p>}
      <Button type="submit" disabled={action.pending || !prompt.trim()}><Sparkles className="mr-2 h-4 w-4" />{t('Generate image', '生成图像')}</Button>
    </form><div className="min-w-0">{history.loading ? <Loading /> : <Tabs defaultValue="images"><TabsList><TabsTrigger value="images">{t('Images', '图像')}</TabsTrigger><TabsTrigger value="jobs">{t('Jobs', '任务')}</TabsTrigger></TabsList><TabsContent value="images"><ImageHistory key={projectId} images={history.data?.images ?? []} refresh={history.refresh} maxUploadMb={config.data?.max_upload_size_mb} /></TabsContent><TabsContent value="jobs"><JobsPanel jobs={history.data?.jobs ?? []} refresh={history.refresh} /></TabsContent></Tabs>}</div></div>
  </div>;
}
