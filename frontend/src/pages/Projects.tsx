import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, FolderOpen, Image, MessageSquare, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { workbenchApi } from '../lib/api';
import { displayDate } from '../lib/workbench';
import { useI18n } from '../lib/i18n';
import { useAction } from '../hooks/useAction';
import { useResource } from '../hooks/useResource';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Empty, ErrorNotice, Field, IconButton, Loading } from '../components/workbench/Common';

export function Projects() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const projects = useResource(workbenchApi.projects, t('Could not load projects.', '无法加载项目。'));
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [field, setField] = useState('');
  return <div className="space-y-5"><header className="flex flex-wrap items-center justify-between gap-3 border-b pb-4"><h1 className="text-xl font-semibold">{t('Projects', '项目')}</h1><div className="flex items-center gap-2"><IconButton label={t('Refresh projects', '刷新项目')} disabled={projects.refreshing} onClick={() => void projects.refresh()}><RefreshCw className="h-4 w-4" /></IconButton><Button onClick={() => { action.setError(''); setOpen(true); }}><Plus className="mr-2 h-4 w-4" />{t('New project', '新建项目')}</Button></div></header>
    <ErrorNotice message={projects.error || (!open ? action.error : '')} />
    {projects.loading ? <Loading /> : !projects.data?.items.length ? <Empty>{t('No projects', '暂无项目')}</Empty> : <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">{projects.data.items.map(project => <article key={project.id} className="min-w-0 rounded-md border p-4"><div className="flex items-start justify-between gap-2"><Link to={`/projects/${project.id}`} className="min-w-0 flex-1 hover:text-primary"><h2 className="flex items-start gap-2 text-base font-semibold"><FolderOpen className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" /><span className="break-words">{project.name}</span></h2></Link><IconButton label={t(`Delete ${project.name}`, `删除 ${project.name}`)} disabled={action.pending} onClick={() => {
      if (!window.confirm(t(`Delete project "${project.name}"?`, `删除项目“${project.name}”？`))) return;
      void action.run(async () => { await workbenchApi.deleteProject(project.id); await projects.refresh(); });
    }}><Trash2 className="h-4 w-4" /></IconButton></div>
      <p className="mt-2 min-h-10 break-words text-sm text-muted-foreground">{project.description || t('No description', '暂无描述')}</p><p className="mt-3 break-words text-xs text-muted-foreground">{project.paper_field} · {displayDate(project.created_at, language)}</p>
      <div className="mt-4 flex flex-wrap gap-4 border-t pt-3 text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5 text-blue-600" />{project.document_count} {t('documents', '文档')}</span><span className="flex items-center gap-1.5"><MessageSquare className="h-3.5 w-3.5 text-emerald-600" />{project.prompt_count} {t('prompts', '提示词')}</span><span className="flex items-center gap-1.5"><Image className="h-3.5 w-3.5 text-rose-600" />{project.image_count} {t('images', '图像')}</span></div>
    </article>)}</div>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>{t('New project', '新建项目')}</DialogTitle><DialogDescription className="sr-only">{t('Project details', '项目详情')}</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => { const project = await workbenchApi.createProject({ name: name.trim(), description: description.trim() || null, paper_field: field.trim() || null, color_scheme: 'okabe-ito' }); setOpen(false); navigate(`/projects/${project.id}`); }); }}>
      <Field label={t('Name', '名称')}><Input value={name} onChange={e => setName(e.target.value)} required maxLength={200} autoFocus disabled={action.pending} /></Field><Field label={t('Description', '描述')}><Textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} disabled={action.pending} /></Field><Field label={t('Research field', '研究领域')}><Input value={field} onChange={e => setField(e.target.value)} disabled={action.pending} /></Field><ErrorNotice message={action.error} /><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={action.pending}>{t('Cancel', '取消')}</Button><Button type="submit" disabled={action.pending || !name.trim()}><Plus className="mr-2 h-4 w-4" />{t('Create project', '创建项目')}</Button></div>
    </form></DialogContent></Dialog>
  </div>;
}
