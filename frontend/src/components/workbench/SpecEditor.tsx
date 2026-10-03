import type { FigureSpec, Section } from '../../lib/types';
import { Trash2 } from 'lucide-react';
import { parseFigureSpec } from '../../lib/figureSpec';
import { useI18n } from '../../lib/i18n';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Field } from './Common';

export function SpecEditor({ text, onChange, sections, disabled }: {
  text: string; onChange: (text: string) => void; sections?: Section[]; disabled: boolean;
}) {
  const { t } = useI18n();
  const parsed = text.trim() ? parseFigureSpec(text, sections) : { spec: undefined, errors: [] };
  const spec = parsed.spec;
  const update = (patch: Partial<FigureSpec>) => { if (spec) onChange(JSON.stringify({ ...spec, ...patch }, null, 2)); };
  return <fieldset className="space-y-4" disabled={disabled}>
    {spec && <>
      <div className="grid gap-3 sm:grid-cols-[1fr_160px]"><Field label={t('Title', '标题')}><Input value={spec.title} onChange={e => update({ title: e.target.value })} /></Field>
        <Field label={t('Direction', '方向')}><select value={spec.direction} onChange={e => update({ direction: e.target.value as FigureSpec['direction'] })}><option value="LR">{t('Left to right', '从左到右')}</option><option value="TB">{t('Top to bottom', '从上到下')}</option></select></Field>
      </div>
      <Field label={t('Caption', '图注')}><Textarea value={spec.caption} onChange={e => update({ caption: e.target.value })} rows={2} /></Field>
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground"><span>{spec.nodes.length} {t('nodes', '节点')}</span><span>{spec.edges.length} {t('edges', '连接')}</span><span>{spec.groups.length} {t('groups', '分组')}</span></div>
    </>}
    <Field label={t('FigureSpec JSON', '图形结构 JSON')}><Textarea spellCheck={false} value={text} onChange={e => onChange(e.target.value)} className="min-h-80 font-mono text-xs" /></Field>
    <Button type="button" variant="outline" size="sm" disabled={disabled || !text.trim()} onClick={() => onChange('')}><Trash2 className="mr-2 h-4 w-4" />{t('Clear FigureSpec', '清除图形结构')}</Button>
    {parsed.errors.length > 0 && <div role="alert" className="max-h-48 overflow-auto rounded-md border border-destructive/30 p-3 text-xs text-destructive"><p className="mb-2 font-semibold">{t('Invalid specification', '图形结构无效')}</p><ul className="list-inside list-disc space-y-1">{parsed.errors.map((error, i) => <li key={i} className="break-words">{error}</li>)}</ul></div>}
    {spec && <details className="border-t pt-3 text-sm"><summary className="cursor-pointer font-medium">{t('Nodes, connections & sources', '节点、连接与来源')}</summary>
      <div className="mt-3 divide-y">{[...spec.nodes, ...spec.edges].map(item => <div key={item.id} className="space-y-1 py-2">
        <p className="break-words font-medium">{item.id}: {item.label || ('source' in item ? `${item.source} → ${item.target}` : '')}</p>
        {'source' in item && <p className="text-xs text-muted-foreground">{item.source} → {item.target} · {item.kind}</p>}
        {item.sources.map((source, i) => <blockquote key={i} className="border-l-2 pl-3 text-xs text-muted-foreground">#{source.section_index} · {source.quote}</blockquote>)}
      </div>)}</div>
    </details>}
  </fieldset>;
}
