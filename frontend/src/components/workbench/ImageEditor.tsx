import { useCallback, useState } from 'react';
import { Send, Upload, X } from 'lucide-react';
import { workbenchApi } from '../../lib/api';
import type { FigureImage } from '../../lib/types';
import type { MaskStroke } from '../../lib/mask';
import { exportMask } from '../../lib/mask';
import { newRequestKey } from '../../lib/workbench';
import { useI18n } from '../../lib/i18n';
import { useAction } from '../../hooks/useAction';
import { useObjectUrl } from '../../hooks/useObjectUrl';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { ErrorNotice, Field, IconButton } from './Common';
import { MaskCanvas } from './MaskCanvas';

export function ImageEditor({ image, url, refresh, maxUploadMb }: { image: FigureImage; url: string; refresh: () => Promise<void>; maxUploadMb?: number }) {
  const { t } = useI18n();
  const action = useAction();
  const [instruction, setInstruction] = useState('');
  const [reference, setReference] = useState<File>();
  const referenceUrl = useObjectUrl(reference);
  const [useMask, setUseMask] = useState(false);
  const [mask, setMask] = useState<{ width: number; height: number; strokes: MaskStroke[] }>({ width: 0, height: 0, strokes: [] });
  const updateMask = useCallback((width: number, height: number, strokes: MaskStroke[]) => setMask({ width, height, strokes }), []);
  const activeUrl = referenceUrl || url;
  return <form className="space-y-4" onSubmit={e => {
    e.preventDefault();
    void action.run(async () => {
      const blob = useMask && mask.strokes.length ? await exportMask(mask.width, mask.height, mask.strokes) : undefined;
      if (blob && maxUploadMb && blob.size > maxUploadMb * 1024 * 1024) throw new Error(t('Mask exceeds the upload limit.', '蒙版超过上传限制。'));
      await workbenchApi.editImage(image.id, { instruction: instruction.trim(), reference, mask: blob, idempotencyKey: newRequestKey() });
      setInstruction('');
      await refresh();
    }, true);
  }}>
    <Field label={t('Edit instruction', '编辑要求')}><Textarea value={instruction} onChange={e => setInstruction(e.target.value)} rows={3} disabled={action.pending} required /></Field>
    <div className="flex flex-wrap items-center gap-2"><label className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm"><Upload className="h-4 w-4" />{t('Reference image', '参考图')}<input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" disabled={action.pending} onChange={e => {
      const file = e.target.files?.[0]; e.target.value = '';
      if (!file) return;
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { action.setError(t('Choose a PNG, JPEG, or WebP image.', '请选择 PNG、JPEG 或 WebP 图像。')); return; }
      if (maxUploadMb && file.size > maxUploadMb * 1024 * 1024) { action.setError(t(`Upload limit: ${maxUploadMb} MB`, `上传限制：${maxUploadMb} MB`)); return; }
      action.setError(''); setMask({ width: 0, height: 0, strokes: [] }); setReference(file);
    }} /></label>
      {reference && <><span className="max-w-full break-words text-xs">{reference.name}</span><IconButton label={t('Remove reference', '移除参考图')} disabled={action.pending} onClick={() => { setReference(undefined); setMask({ width: 0, height: 0, strokes: [] }); }}><X className="h-4 w-4" /></IconButton></>}
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useMask} onChange={e => setUseMask(e.target.checked)} disabled={action.pending || !activeUrl} />{t('Edit mask', '编辑蒙版')}</label>
    {useMask && activeUrl ? <MaskCanvas key={activeUrl} url={activeUrl} onChange={updateMask} disabled={action.pending} /> : referenceUrl && <img src={referenceUrl} alt={t('Reference image', '参考图')} className="max-h-80 w-full object-contain" />}
    <ErrorNotice message={action.error} unknown={action.unknown} />
    <Button type="submit" disabled={action.pending || !instruction.trim() || !activeUrl || (useMask && (!mask.width || !mask.strokes.length))}><Send className="mr-2 h-4 w-4" />{t('Create edited version', '生成编辑版本')}</Button>
  </form>;
}
