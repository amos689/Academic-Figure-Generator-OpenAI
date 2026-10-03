import { useState } from 'react';
import { Download, FileDown } from 'lucide-react';
import type { ExportFormat, FigureExport, FigureSpec } from '../../lib/types';
import { workbenchApi } from '../../lib/api';
import { fetchAuthedBlob, triggerBrowserDownload } from '../../lib/blob';
import { completedStatus, displayDate, newRequestKey, nonSecret } from '../../lib/workbench';
import { useAction } from '../../hooks/useAction';
import { useI18n } from '../../lib/i18n';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Empty, ErrorNotice, Field, IconButton, StatusBadge } from './Common';

export function ExportControls({ promptId, spec, dirty, refresh }: { promptId: string; spec?: FigureSpec; dirty: boolean; refresh: () => Promise<void> }) {
  const { t } = useI18n();
  const [format, setFormat] = useState<ExportFormat>('svg');
  const [width, setWidth] = useState(1600);
  const action = useAction();
  return <form className="space-y-3 border-t pt-4" onSubmit={e => {
    e.preventDefault();
    if (!spec || dirty) return;
    void action.run(async () => {
      await workbenchApi.exportFigure(promptId, { format, width, figure_spec: spec, idempotency_key: newRequestKey() });
      await refresh();
    });
  }}>
    <h3 className="text-sm font-semibold">{t('Vector export', '矢量导出')}</h3>
    <div className="grid gap-3 sm:grid-cols-2"><Field label={t('Format', '格式')}><select value={format} onChange={e => setFormat(e.target.value as ExportFormat)} disabled={action.pending}><option value="svg">SVG</option><option value="pdf">PDF</option><option value="drawio">draw.io</option></select></Field>
      <Field label={t('Width (px)', '宽度（像素）')}><Input type="number" value={width} min={640} max={4096} step={1} required onChange={e => setWidth(Number(e.target.value))} disabled={action.pending} /></Field></div>
    <ErrorNotice message={action.error} />
    <Button type="submit" variant="outline" disabled={action.pending || !spec || dirty || !Number.isInteger(width) || width < 640 || width > 4096}><FileDown className="mr-2 h-4 w-4" />{t('Export figure', '导出图形')}</Button>
    {dirty && <p className="text-xs text-muted-foreground">{t('Unsaved revision', '修订尚未保存')}</p>}
  </form>;
}

export function ExportHistory({ exports }: { exports: FigureExport[] }) {
  const { t, language } = useI18n();
  const action = useAction();
  return <section aria-label={t('Export history', '导出历史')} className="space-y-3">
    <ErrorNotice message={action.error} />
    {!exports.length && <Empty>{t('No exports', '暂无导出记录')}</Empty>}
    <ul className="divide-y">{exports.map(item => <li key={item.id} className="space-y-2 py-4"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium uppercase">{item.format}</span><StatusBadge status={item.generation_status} /><span className="text-xs text-muted-foreground">{item.width_px ?? '-'} × {item.height_px ?? '-'}</span></div><p className="mt-2 break-all text-xs text-muted-foreground">{displayDate(item.created_at, language)} · {item.prompt_id}</p></div>
      {completedStatus(item.generation_status) && <IconButton label={t('Download export', '下载导出文件')} disabled={action.pending} onClick={() => void action.run(async () => { const { blob } = await fetchAuthedBlob(`/exports/${encodeURIComponent(item.id)}/download`); triggerBrowserDownload(blob, `figure-${item.id}.${item.format}`); })}><Download className="h-4 w-4" /></IconButton>}
    </div>{item.prompt_revision != null && <p className="text-xs text-muted-foreground">{t('Prompt revision', '提示词修订')}: {item.prompt_revision}</p>}<ErrorNotice message={item.generation_error ?? ''} />{item.generation_metadata && <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">{t('Export settings', '导出设置')}</summary><pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(nonSecret(item.generation_metadata), null, 2)}</pre></details>}</li>)}</ul>
  </section>;
}
