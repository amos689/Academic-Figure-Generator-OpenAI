import { useRef, useState } from 'react';
import { FileUp, Send } from 'lucide-react';
import { workbenchApi } from '../../lib/api';
import type { ColorScheme, DocumentItem, GenerationSettings } from '../../lib/types';
import { completedStatus, newRequestKey, sectionIndex, withPalette } from '../../lib/workbench';
import { useI18n } from '../../lib/i18n';
import { useAction } from '../../hooks/useAction';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Input } from '../ui/input';
import { Empty, ErrorNotice, Field, StatusBadge } from './Common';
import { GenerationControls } from './GenerationControls';

interface Props {
  projectId: string;
  documents: DocumentItem[];
  settings: GenerationSettings;
  onSettings: (settings: GenerationSettings) => void;
  palettes: ColorScheme[];
  maxUploadMb?: number;
  refresh: () => Promise<void>;
}

export function DocumentsPanel(props: Props) {
  const { t } = useI18n();
  const upload = useAction();
  const fileInput = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState(0);
  const [selected, setSelected] = useState('');
  const document = props.documents.find(doc => doc.id === selected);
  async function uploadFile(file?: File) {
    if (!file) return;
    if (!/\.(pdf|docx|txt)$/i.test(file.name)) {
      upload.setError(t('Choose a PDF, DOCX, or TXT file.', '请选择 PDF、DOCX 或 TXT 文件。'));
      return;
    }
    if (props.maxUploadMb && file.size > props.maxUploadMb * 1024 * 1024) {
      upload.setError(t(`Upload limit: ${props.maxUploadMb} MB`, `上传限制：${props.maxUploadMb} MB`)); return;
    }
    setProgress(0);
    await upload.run(async () => {
      await workbenchApi.uploadDocument(props.projectId, file, setProgress);
      await props.refresh();
    });
  }
  return <section className="space-y-5" aria-label={t('Documents', '文档')}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-base font-semibold">{t('Source documents', '源文档')}</h2>
      <Button variant="outline" disabled={upload.pending} onClick={() => fileInput.current?.click()}><FileUp className="mr-2 h-4 w-4" />{upload.pending ? `${progress}%` : t('Upload', '上传')}</Button>
      <input ref={fileInput} type="file" accept=".pdf,.docx,.txt" className="hidden" aria-label={t('Upload document', '上传文档')} onChange={e => { void uploadFile(e.target.files?.[0]); e.target.value = ''; }} />
    </div>
    <ErrorNotice message={upload.error} />
    {!props.documents.length ? <Empty>{t('No documents', '暂无文档')}</Empty> : <ul className="divide-y border-y">
      {props.documents.map(doc => <li key={doc.id} className="space-y-2 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><p className="break-words text-sm font-medium">{doc.original_filename}</p><p className="mt-1 text-xs text-muted-foreground">{(doc.file_size_bytes / 1024).toFixed(0)} KB{doc.page_count ? ` · ${doc.page_count} ${t('pages', '页')}` : ''}</p></div><StatusBadge status={doc.parse_status} /></div>
        <ErrorNotice message={doc.parse_error ?? ''} />
      </li>)}
    </ul>}
    <Field label={t('Source document', '选择源文档')}><select value={selected} onChange={e => setSelected(e.target.value)}>
      <option value="">{t('Choose a document', '请选择文档')}</option>
      {props.documents.map(doc => <option key={doc.id} value={doc.id} disabled={!completedStatus(doc.parse_status)}>{doc.original_filename}</option>)}
    </select></Field>
    {document && completedStatus(document.parse_status) && <PromptRequest key={document.id} {...props} document={document} />}
  </section>;
}

function PromptRequest({ document, settings, onSettings, palettes, projectId, refresh }: Props & { document: DocumentItem }) {
  const { t } = useI18n();
  const action = useAction();
  const [mode, setMode] = useState('all');
  const [indices, setIndices] = useState<number[]>([]);
  const [request, setRequest] = useState('');
  const [count, setCount] = useState(1);
  const [template, setTemplate] = useState(false);
  const [figureTypes, setFigureTypes] = useState<string[]>([]);
  const sections = document.sections ?? [];
  const types = [
    ['overall_framework', t('Framework', '总体框架')], ['network_architecture', t('Architecture', '网络架构')],
    ['module_detail', t('Module detail', '模块细节')],
    ['comparison_ablation', t('Comparison / ablation', '比较 / 消融')], ['data_behavior', t('Data / behavior', '数据 / 行为')],
  ];
  return <form className="space-y-4 border-t pt-4" onSubmit={e => {
    e.preventDefault();
    void action.run(async () => {
      const resolved = withPalette(settings, palettes);
      await workbenchApi.promptJob(projectId, {
        document_id: document.id, section_indices: mode === 'all' ? null : indices,
        color_scheme: resolved.color_scheme, custom_colors: resolved.custom_colors,
        style_preset: resolved.style_preset, profile: resolved.profile,
        figure_types: figureTypes.length ? figureTypes : null, user_request: request.trim(),
        max_figures: count, template_mode: template, idempotency_key: newRequestKey(),
      });
      await refresh();
    }, true);
  }}>
    <Field label={t('Scope', '范围')}><select value={mode} onChange={e => setMode(e.target.value)} disabled={action.pending}>
      <option value="all">{t('Entire document', '全文')}</option><option value="sections">{t('Selected sections', '指定章节')}</option>
    </select></Field>
    {mode === 'sections' && <fieldset disabled={action.pending} className="max-h-80 overflow-y-auto rounded-md border p-2">
      <legend className="px-1 text-xs text-muted-foreground">{t('Sections', '章节')} ({indices.length}/{sections.length})</legend>
      <div className="mb-2 flex gap-3 text-xs"><button type="button" className="text-primary underline" onClick={() => setIndices(sections.map(sectionIndex))}>{t('All', '全选')}</button><button type="button" className="text-primary underline" onClick={() => setIndices([])}>{t('None', '清空')}</button></div>
      {sections.map((section, position) => {
        const index = sectionIndex(section, position);
        return <div key={index} className="border-t py-2" style={{ paddingLeft: Math.min(3, Math.max(0, (section.level ?? 1) - 1)) * 10 }}>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={indices.includes(index)} onChange={e => setIndices(prev => e.target.checked ? [...prev, index] : prev.filter(i => i !== index))} /><span className="min-w-0 break-words">{section.title || `${t('Section', '章节')} ${index}`}</span></label>
          <details className="ml-5 mt-1 text-xs text-muted-foreground"><summary className="cursor-pointer">{t('Source', '原文')} #{index}</summary><pre className="mt-2 whitespace-pre-wrap break-words font-sans">{section.content || section.text}</pre></details>
        </div>;
      })}
      {!sections.length && <Empty>{t('No parsed sections', '暂无解析章节')}</Empty>}
    </fieldset>}
    <Field label={t('Figure request', '配图需求')}><Textarea value={request} onChange={e => setRequest(e.target.value)} rows={4} maxLength={6000} disabled={action.pending} /></Field>
    <fieldset className="space-y-2" disabled={action.pending}><legend className="mb-2 text-sm font-medium">{t('Figure types', '图形类型')}</legend>
      {types.map(([value, label]) => <label key={value} className="mr-4 inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={figureTypes.includes(value)} onChange={e => setFigureTypes(previous => e.target.checked ? [...previous, value] : previous.filter(v => v !== value))} />{label}</label>)}
    </fieldset>
    <Field label={t('Maximum figures', '最多配图数')}><Input type="number" min={1} max={8} value={count} onChange={e => setCount(Number(e.target.value))} required disabled={action.pending} /></Field>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={template} onChange={e => setTemplate(e.target.checked)} disabled={action.pending} />{t('Template mode', '模板模式')}</label>
    <GenerationControls value={settings} onChange={onSettings} palettes={palettes} image={false} disabled={action.pending} />
    <ErrorNotice message={action.error} unknown={action.unknown} />
    <Button type="submit" disabled={action.pending || (mode === 'sections' && !indices.length) || !Number.isInteger(count) || count < 1 || count > 8} className="w-full"><Send className="mr-2 h-4 w-4" />{t('Generate prompts', '生成提示词')}</Button>
  </form>;
}
