import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Save } from 'lucide-react';
import type { ColorScheme, GenerationSettings, Project } from '../lib/types';
import { workbenchApi } from '../lib/api';
import { DEFAULT_SETTINGS, withPalette } from '../lib/workbench';
import { useI18n } from '../lib/i18n';
import { useResource } from '../hooks/useResource';
import { useWorkspace } from '../hooks/useWorkspace';
import { useAction } from '../hooks/useAction';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Empty, ErrorNotice, Field, IconButton, Loading } from '../components/workbench/Common';
import { DocumentsPanel } from '../components/workbench/DocumentsPanel';
import { GenerationControls } from '../components/workbench/GenerationControls';
import { PromptEditor } from '../components/workbench/PromptEditor';
import { ImageHistory } from '../components/workbench/ImageHistory';
import { JobsPanel } from '../components/workbench/JobsPanel';
import { ExportHistory } from '../components/workbench/ExportPanel';

export function ProjectWorkspace() {
  const { id } = useParams();
  return id ? <Workspace key={id} id={id} /> : null;
}

function Workspace({ id }: { id: string }) {
  const { t } = useI18n();
  const workspace = useWorkspace(id);
  const palettes = useResource(workbenchApi.palettes, t('Could not load palettes.', '无法加载配色。'));
  const config = useResource(workbenchApi.configuration, t('Could not load effective settings.', '无法加载有效配置。'));
  if (workspace.loading) return <Loading />;
  if (!workspace.data) return <div className="space-y-3"><ErrorNotice message={workspace.error} /><Button variant="outline" onClick={() => void workspace.refresh()}><RefreshCw className="mr-2 h-4 w-4" />{t('Reload', '重新加载')}</Button></div>;
  return <WorkspaceBody project={workspace.data.project} workspace={workspace} palettes={palettes.data ?? []} maxUploadMb={config.data?.max_upload_size_mb} settingsError={palettes.error || config.error} />;
}

function WorkspaceBody({ project, workspace, palettes, maxUploadMb, settingsError }: {
  project: Project; workspace: ReturnType<typeof useWorkspace>; palettes: ColorScheme[]; maxUploadMb?: number; settingsError: string;
}) {
  const { t } = useI18n();
  const data = workspace.data!;
  const [settings, setSettings] = useState<GenerationSettings>(() => ({ ...DEFAULT_SETTINGS, color_scheme: project.color_scheme, custom_colors: project.custom_colors ?? undefined, style_preset: project.style_preset ?? 'classic' }));
  const [promptSettings, setPromptSettings] = useState<Record<string, GenerationSettings>>({});
  const [promptId, setPromptId] = useState('');
  const [tab, setTab] = useState('prompts');
  const defaults = useAction();
  const currentPrompt = data.prompts.find(p => p.id === promptId) ?? data.prompts[0];
  return <div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3 border-b pb-4"><div className="flex min-w-0 flex-1 items-start gap-3"><Button asChild variant="ghost" size="icon" aria-label={t('Back to projects', '返回项目')}><Link to="/projects"><ArrowLeft className="h-4 w-4" /></Link></Button><div className="min-w-0"><h1 className="break-words text-xl font-semibold">{project.name}</h1>{project.description && <p className="mt-1 break-words text-sm text-muted-foreground">{project.description}</p>}</div></div><IconButton label={t('Refresh workspace', '刷新工作区')} disabled={workspace.refreshing} onClick={() => void workspace.refresh()}><RefreshCw className={`h-4 w-4 ${workspace.refreshing ? 'animate-spin' : ''}`} /></IconButton></header>
    <ErrorNotice message={workspace.error || settingsError} />
    {!!data.unavailable.length && <ErrorNotice message={`${t('Some resources could not be refreshed', '部分资源无法刷新')}: ${data.unavailable.join(', ')}`} />}
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(280px,320px)_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-5 xl:border-r xl:pr-5">
        <DocumentsPanel projectId={project.id} documents={data.documents} settings={settings} onSettings={setSettings} palettes={palettes} maxUploadMb={maxUploadMb} refresh={workspace.refresh} />
        <details className="border-t pt-4"><summary className="cursor-pointer text-sm font-semibold">{t('Project defaults', '项目默认设置')}</summary><div className="mt-4 space-y-3"><GenerationControls value={settings} onChange={setSettings} palettes={palettes} image={false} disabled={defaults.pending} /><ErrorNotice message={defaults.error} /><Button variant="outline" disabled={defaults.pending} onClick={() => void defaults.run(async () => {
          const resolved = withPalette(settings, palettes);
          await workbenchApi.updateProject(project.id, { color_scheme: resolved.color_scheme, custom_colors: resolved.custom_colors, style_preset: resolved.style_preset });
          await workspace.refresh();
        })}><Save className="mr-2 h-4 w-4" />{t('Save defaults', '保存默认设置')}</Button></div></details>
      </aside>
      <div className="min-w-0"><Tabs value={tab} onValueChange={setTab} className="min-w-0"><TabsList className="mb-3 flex h-auto w-full flex-wrap justify-start gap-1 bg-transparent p-0">
        <TabsTrigger value="prompts">{t('Prompts', '提示词')} ({data.prompts.length})</TabsTrigger><TabsTrigger value="images">{t('Images', '图像')} ({data.images.length})</TabsTrigger><TabsTrigger value="jobs">{t('Jobs', '任务')} ({data.jobs.length})</TabsTrigger><TabsTrigger value="exports">{t('Exports', '导出')} ({data.exports.length})</TabsTrigger>
      </TabsList>
        <TabsContent value="prompts" forceMount className="space-y-5 data-[state=inactive]:hidden">
          {!data.prompts.length ? <Empty>{t('No prompts', '暂无提示词')}</Empty> : <><Field label={t('Figure', '配图')}><select value={currentPrompt?.id ?? ''} onChange={e => setPromptId(e.target.value)}>{data.prompts.map(prompt => <option key={prompt.id} value={prompt.id}>{prompt.figure_number}. {prompt.title || t('Untitled', '未命名')}</option>)}</select></Field>
            {data.prompts.map(prompt => <div key={prompt.id} hidden={prompt.id !== currentPrompt?.id}><PromptEditor prompt={prompt} document={data.documents.find(d => d.id === prompt.document_id)} settings={promptSettings[prompt.id] ?? { ...settings, aspect_ratio: prompt.suggested_aspect_ratio || settings.aspect_ratio, style_preset: prompt.style_preset ?? settings.style_preset }} onSettings={value => setPromptSettings(previous => ({ ...previous, [prompt.id]: value }))} palettes={palettes} refresh={workspace.refresh} /></div>)}</>}
        </TabsContent>
        <TabsContent value="images"><ImageHistory images={data.images} refresh={workspace.refresh} maxUploadMb={maxUploadMb} /></TabsContent>
        <TabsContent value="jobs"><JobsPanel jobs={data.jobs} refresh={workspace.refresh} /></TabsContent>
        <TabsContent value="exports"><ExportHistory exports={data.exports} /></TabsContent>
      </Tabs></div>
    </div>
  </div>;
}
