import { useCallback, useEffect, useState } from 'react';
import { Copy, History, RotateCcw, Save, Sparkles } from 'lucide-react';
import type { ColorScheme, DocumentItem, GenerationSettings, Prompt } from '../../lib/types';
import { workbenchApi } from '../../lib/api';
import { isRevisionConflict } from '../../lib/apiError';
import { parseFigureSpec } from '../../lib/figureSpec';
import { figureSpecChanged, figureSpecPatch, readPromptDraft, storePromptDraft } from '../../lib/promptDraft';
import { displayDate, newRequestKey, nonSecret, promptText, withPalette } from '../../lib/workbench';
import { useI18n } from '../../lib/i18n';
import { useAction } from '../../hooks/useAction';
import { useResource } from '../../hooks/useResource';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { ErrorNotice, Field, IconButton, Loading } from './Common';
import { GenerationControls } from './GenerationControls';
import { SpecEditor } from './SpecEditor';
import { ExportControls } from './ExportPanel';

const snapshot = (prompt: Prompt) => ({ text: promptText(prompt), spec: prompt.figure_spec ? JSON.stringify(prompt.figure_spec, null, 2) : '', revision: prompt.revision ?? 1 });

export function PromptEditor({ prompt, document, settings, onSettings, palettes, refresh }: {
  prompt: Prompt; document?: DocumentItem; settings: GenerationSettings; onSettings: (value: GenerationSettings) => void; palettes: ColorScheme[]; refresh: () => Promise<void>;
}) {
  const { t } = useI18n();
  const [initial] = useState(() => readPromptDraft(prompt.id, snapshot(prompt)));
  const [base, setBase] = useState(initial.base);
  const [text, setText] = useState(initial.text);
  const [specText, setSpecText] = useState(initial.spec);
  const [conflict, setConflict] = useState(false);
  const [history, setHistory] = useState(false);
  const action = useAction();
  const specChanged = figureSpecChanged(base.spec, specText);
  const dirty = text !== base.text || specChanged;
  const outdated = conflict || (prompt.revision ?? 1) > base.revision;
  const parsedSpec = specText.trim() ? parseFigureSpec(specText, document?.sections ?? undefined) : { spec: undefined, errors: [] };
  useEffect(() => { storePromptDraft(prompt.id, { base, text, spec: specText }); }, [prompt.id, base, text, specText]);

  if ((prompt.revision ?? 1) > base.revision && !dirty) {
    const next = snapshot(prompt);
    setBase(next); setText(next.text); setSpecText(next.spec); setConflict(false);
  }

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  async function save() {
    await action.run(async () => {
      try {
        const result = await workbenchApi.savePrompt(prompt.id, {
          edited_prompt: text, expected_revision: base.revision,
          ...figureSpecPatch(base.spec, specText, parsedSpec.spec),
        });
        const next = snapshot(result);
        setBase(next); setText(next.text); setSpecText(next.spec); setConflict(false);
        await refresh();
      } catch (cause) {
        if (isRevisionConflict(cause)) { setConflict(true); await refresh(); }
        throw cause;
      }
    });
  }

  return <article className="min-w-0 space-y-4" aria-label={prompt.title || `${t('Figure', '配图')} ${prompt.figure_number}`}>
    <header className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><h2 className="break-words text-base font-semibold">{prompt.title || `${t('Figure', '配图')} ${prompt.figure_number}`}</h2><p className="mt-1 break-words text-xs text-muted-foreground">{t('Revision', '修订')} {base.revision} · {prompt.generation_model || prompt.claude_model || t('Model unavailable', '模型未知')}{dirty ? ` · ${t('Unsaved', '未保存')}` : ''}</p></div>
      <div className="flex shrink-0 gap-1"><IconButton label={t('Copy prompt', '复制提示词')} onClick={() => void action.run(async () => navigator.clipboard.writeText(text))}><Copy className="h-4 w-4" /></IconButton><IconButton label={t('Revision history', '修订历史')} onClick={() => setHistory(true)}><History className="h-4 w-4" /></IconButton></div>
    </header>
    {outdated && <div role="alert" className="space-y-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p>{t('This prompt changed on the server. Your draft is preserved.', '服务器上的提示词已更新，您的草稿已保留。')}</p>
      <details><summary className="cursor-pointer">{t('Latest saved prompt', '最新已保存提示词')} ({prompt.revision})</summary><pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words font-sans text-xs">{promptText(prompt)}</pre></details>
      {prompt.figure_spec && <details><summary className="cursor-pointer">{t('Latest saved FigureSpec', '最新已保存图形结构')}</summary><pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(prompt.figure_spec, null, 2)}</pre></details>}
      <div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => {
        if (!window.confirm(t('Discard this local draft and load the saved revision?', '放弃本地草稿并载入已保存修订？'))) return;
        const next = snapshot(prompt); setBase(next); setText(next.text); setSpecText(next.spec); setConflict(false); action.setError('');
      }}>{t('Load saved revision', '载入已保存修订')}</Button>
        <Button variant="outline" size="sm" disabled={(prompt.revision ?? 1) <= base.revision} onClick={() => { setBase(snapshot(prompt)); setConflict(false); action.setError(''); }}>{t('Keep draft on latest revision', '保留草稿并基于最新修订')}</Button>
      </div>
    </div>}
    <ErrorNotice message={action.error} unknown={action.unknown} />
    <Tabs defaultValue="prompt" className="min-w-0"><TabsList className="max-w-full"><TabsTrigger value="prompt">{t('Prompt', '提示词')}</TabsTrigger><TabsTrigger value="spec">FigureSpec</TabsTrigger><TabsTrigger value="inputs">{t('Sources', '来源')}</TabsTrigger></TabsList>
      <TabsContent value="prompt" className="space-y-4"><Field label={t('Prompt text', '提示词内容')}><Textarea value={text} onChange={e => setText(e.target.value)} className="min-h-72 text-sm leading-relaxed" maxLength={60000} disabled={action.pending} /></Field></TabsContent>
      <TabsContent value="spec" className="space-y-4">
        <SpecEditor text={specText} onChange={setSpecText} sections={document?.sections ?? undefined} disabled={action.pending} />
        {specChanged && !specText.trim() && <p role="status" className="text-sm text-muted-foreground">{t('FigureSpec will be cleared on save.', '保存后将清除现有图形结构。')}</p>}
        {!base.spec.trim() && !specText.trim() && <div className="space-y-3 py-4"><p className="text-sm text-muted-foreground">{t('No editable specification', '暂无可编辑结构')}</p><Button variant="outline" disabled={action.pending || dirty || outdated} onClick={() => void action.run(async () => { await workbenchApi.specJob(prompt.id, newRequestKey()); await refresh(); }, true)}><Sparkles className="mr-2 h-4 w-4" />{t('Derive FigureSpec', '生成图形结构')}</Button></div>}
        <ExportControls promptId={prompt.id} spec={parsedSpec.spec} dirty={dirty || outdated} refresh={refresh} />
      </TabsContent>
      <TabsContent value="inputs" className="space-y-3"><p className="break-words text-sm">{document?.original_filename || prompt.document_id || t('Direct input', '直接输入')}</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs">{JSON.stringify(nonSecret(prompt.source_sections), null, 2)}</pre>{prompt.generation_metadata && <details className="text-sm"><summary className="cursor-pointer">{t('Generation settings', '生成设置')}</summary><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(nonSecret(prompt.generation_metadata), null, 2)}</pre></details>}</TabsContent>
    </Tabs>
    <div className="flex flex-wrap items-center gap-2"><Button variant="outline" onClick={() => void save()} disabled={action.pending || !dirty || outdated || !text.trim() || (specChanged && !!parsedSpec.errors.length)}><Save className="mr-2 h-4 w-4" />{t('Save revision', '保存修订')}</Button>
      <IconButton label={t('Discard local changes', '放弃本地更改')} disabled={!dirty || action.pending} onClick={() => { if (window.confirm(t('Discard unsaved changes?', '放弃未保存更改？'))) { setText(base.text); setSpecText(base.spec); } }}><RotateCcw className="h-4 w-4" /></IconButton>
    </div>
    {text !== base.text && !!base.spec.trim() && !specChanged && <p className="text-xs text-muted-foreground">{t('FigureSpec will be invalidated by this text-only revision.', '仅修改提示词的修订将使原有图形结构失效。')}</p>}
    <div className="space-y-4 border-t pt-4"><GenerationControls value={settings} onChange={onSettings} palettes={palettes} disabled={action.pending} /><Button disabled={action.pending || dirty || outdated || !text.trim()} onClick={() => void action.run(async () => { await workbenchApi.imageJob(prompt.id, { ...withPalette(settings, palettes), idempotency_key: newRequestKey() }); await refresh(); }, true)}><Sparkles className="mr-2 h-4 w-4" />{t('Generate image', '生成图像')}</Button></div>
    <Dialog open={history} onOpenChange={setHistory}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{t('Revision history', '修订历史')}</DialogTitle><DialogDescription>{prompt.title}</DialogDescription></DialogHeader>{history && <RevisionHistory prompt={prompt} disabled={dirty || outdated || action.pending} onConflict={refresh} onRestore={async result => { const next = snapshot(result); setBase(next); setText(next.text); setSpecText(next.spec); setConflict(false); setHistory(false); await refresh(); }} />}</DialogContent></Dialog>
  </article>;
}

function RevisionHistory({ prompt, disabled, onRestore, onConflict }: { prompt: Prompt; disabled: boolean; onRestore: (prompt: Prompt) => Promise<void>; onConflict: () => Promise<void> }) {
  const { t, language } = useI18n();
  const load = useCallback((signal: AbortSignal) => workbenchApi.revisions(prompt.id, signal), [prompt.id]);
  const history = useResource(load, t('Could not load revisions.', '无法加载修订历史。'));
  const action = useAction();
  return <div className="space-y-3"><ErrorNotice message={history.error || action.error} />{history.loading && <Loading />}{disabled && <p className="text-sm text-muted-foreground">{t('Resolve unsaved changes before restoring.', '请先处理未保存的更改，再恢复历史版本。')}</p>}
    {history.data?.map(revision => <div key={revision.id} className="space-y-3 border-t py-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">{t('Revision', '修订')} {revision.revision} <span className="text-xs font-normal text-muted-foreground">{displayDate(revision.created_at, language)}</span></p><Button size="sm" variant="outline" disabled={disabled || action.pending || revision.revision === prompt.revision} onClick={() => {
      if (!window.confirm(t('Restore this revision as a new revision?', '将此版本恢复为新的修订？'))) return;
      void action.run(async () => {
        try { await onRestore(await workbenchApi.restorePrompt(prompt.id, revision.revision, prompt.revision)); }
        catch (cause) { if (isRevisionConflict(cause)) await onConflict(); throw cause; }
      });
    }}><RotateCcw className="mr-2 h-3 w-3" />{t('Restore', '恢复')}</Button></div><pre className="max-h-52 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-sans text-xs">{revision.prompt_text}</pre>{revision.figure_spec && <details className="text-xs"><summary className="cursor-pointer">FigureSpec</summary><pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(revision.figure_spec, null, 2)}</pre></details>}</div>)}
  </div>;
}
