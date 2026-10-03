import { useCallback, useState } from 'react';
import { Check, Columns2, Download, GitBranch, Maximize2, RefreshCw, Star } from 'lucide-react';
import type { FigureImage } from '../../lib/types';
import { workbenchApi } from '../../lib/api';
import { fetchAuthedBlob, triggerBrowserDownload } from '../../lib/blob';
import { completedStatus, displayDate, imageAncestors, nonSecret } from '../../lib/workbench';
import { useI18n } from '../../lib/i18n';
import { useAction } from '../../hooks/useAction';
import { useImageBlob } from '../../hooks/useImageBlob';
import { useResource } from '../../hooks/useResource';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Empty, ErrorNotice, Field, IconButton, Loading, StatusBadge } from './Common';
import { ImageEditor } from './ImageEditor';

export function FigurePreview({ image, large = false }: { image: FigureImage; large?: boolean }) {
  const { t } = useI18n();
  const preview = useImageBlob(image.id);
  return <div className={`flex w-full items-center justify-center overflow-hidden bg-muted/30 ${large ? 'min-h-48' : 'aspect-[4/3]'}`}>
    {preview.error ? <div className="p-3 text-center text-xs"><p>{preview.error}</p><IconButton label={t('Reload preview', '重新加载预览')} onClick={() => void preview.refresh()}><RefreshCw className="h-4 w-4" /></IconButton></div> : preview.url ? <img src={preview.url} alt={`${t('Figure', '图像')} ${image.id}`} className={`block w-full object-contain ${large ? 'max-h-[65vh]' : 'h-full'}`} /> : <Loading />}
  </div>;
}

export function ImageHistory({ images, refresh, maxUploadMb }: { images: FigureImage[]; refresh: () => Promise<void>; maxUploadMb?: number }) {
  const { t, language } = useI18n();
  const [filter, setFilter] = useState('all');
  const [activeId, setActiveId] = useState<string>();
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const action = useAction();
  const active = images.find(image => image.id === activeId);
  const visible = images.filter(image => filter === 'all' || (filter === 'favorite' ? image.favorite : image.selected));
  const compared = compareIds.map(id => images.find(image => image.id === id)).filter((item): item is FigureImage => !!item);
  return <section className="space-y-4" aria-label={t('Image history', '图像历史')}>
    <div className="flex flex-wrap items-end justify-between gap-3"><div className="w-44"><Field label={t('Image history', '图像历史')}><select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">{t('All images', '全部图像')}</option><option value="favorite">{t('Favorites', '收藏')}</option><option value="selected">{t('Selected', '已选用')}</option></select></Field></div><Button variant="outline" disabled={compared.length !== 2} onClick={() => setCompareOpen(true)}><Columns2 className="mr-2 h-4 w-4" />{t('Compare', '比较')} ({compared.length}/2)</Button></div>
    <ErrorNotice message={action.error} />
    {!visible.length && <Empty>{t('No images', '暂无图像')}</Empty>}
    <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-3">{visible.map((image, index) => <article key={image.id} className={`min-w-0 overflow-hidden rounded-md border ${image.selected ? 'border-emerald-500' : ''}`}>
      {completedStatus(image.generation_status) ? <button type="button" className="block w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary" onClick={() => setActiveId(image.id)} aria-label={`${t('Inspect image', '查看图像')} ${index + 1}`}><FigurePreview image={image} /></button> : <div className="flex aspect-[4/3] items-center justify-center bg-muted/30"><StatusBadge status={image.generation_status} /></div>}
      <div className="space-y-2 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><StatusBadge status={image.generation_status} /><span className="text-xs text-muted-foreground">{image.width_px && image.height_px ? `${image.width_px} × ${image.height_px}` : image.resolution}</span></div>
        <p className="break-words text-xs text-muted-foreground">{displayDate(image.created_at, language)} · {image.id.slice(0, 8)}</p>
        {image.parent_image_id && <p className="flex items-center gap-1 text-xs text-muted-foreground"><GitBranch className="h-3 w-3" />{t('From', '来源')} {image.parent_image_id.slice(0, 8)}</p>}
        <ErrorNotice message={image.generation_error ?? ''} />
        <div className="flex flex-wrap items-center justify-between gap-1"><div className="flex gap-1"><IconButton label={image.favorite ? t('Remove favorite', '取消收藏') : t('Favorite', '收藏')} aria-pressed={!!image.favorite} disabled={action.pending} onClick={() => void action.run(async () => { await workbenchApi.updateImage(image.id, { favorite: !image.favorite }); await refresh(); })}><Star className={`h-4 w-4 ${image.favorite ? 'fill-amber-400 text-amber-600' : ''}`} /></IconButton>
          <IconButton label={image.selected ? t('Deselect image', '取消选用') : t('Select image', '选用图像')} aria-pressed={!!image.selected} disabled={action.pending || !completedStatus(image.generation_status)} onClick={() => void action.run(async () => { await workbenchApi.updateImage(image.id, { selected: !image.selected }); await refresh(); })}><Check className={`h-4 w-4 ${image.selected ? 'text-emerald-600' : ''}`} /></IconButton>
          {completedStatus(image.generation_status) && <IconButton label={t('Download image', '下载图像')} disabled={action.pending} onClick={() => void action.run(async () => { const { blob, ext } = await fetchAuthedBlob(`/images/${encodeURIComponent(image.id)}/download`); triggerBrowserDownload(blob, `figure-${image.id}.${ext}`); })}><Download className="h-4 w-4" /></IconButton>}
        </div>{completedStatus(image.generation_status) && <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" aria-label={`${t('Compare image', '比较图像')} ${index + 1}`} checked={compareIds.includes(image.id)} disabled={!compareIds.includes(image.id) && compareIds.length >= 2} onChange={e => setCompareIds(previous => e.target.checked ? [...previous, image.id] : previous.filter(id => id !== image.id))} />{t('Compare', '比较')}</label>}</div>
      </div>
    </article>)}</div>
    <Dialog open={!!active} onOpenChange={open => { if (!open) setActiveId(undefined); }}><DialogContent className="max-w-5xl"><DialogHeader><DialogTitle>{t('Image details', '图像详情')}</DialogTitle><DialogDescription className="break-all">{active?.id}</DialogDescription></DialogHeader>{active && <ImageInspector key={active.id} image={active} images={images} onSelect={setActiveId} refresh={refresh} maxUploadMb={maxUploadMb} />}</DialogContent></Dialog>
    <Dialog open={compareOpen} onOpenChange={setCompareOpen}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>{t('Image comparison', '图像比较')}</DialogTitle><DialogDescription>{t('Saved versions', '已保存版本')}</DialogDescription></DialogHeader><div className="grid min-w-0 gap-4 md:grid-cols-2">{compared.map(image => <div key={image.id} className="min-w-0 space-y-3"><FigurePreview image={image} large /><ImageMetadata image={image} /></div>)}</div></DialogContent></Dialog>
  </section>;
}

function ImageMetadata({ image }: { image: FigureImage }) {
  const { t, language } = useI18n();
  const data = [
    [t('Model', '模型'), image.generation_model], [t('Quality', '质量'), image.quality],
    [t('Style', '风格'), image.style_preset], [t('Palette', '配色'), image.color_scheme],
    [t('Prompt revision', '提示词修订'), image.prompt_revision], [t('Duration', '耗时'), image.generation_duration_ms == null ? null : `${(image.generation_duration_ms / 1000).toFixed(1)}s`],
    [t('Created', '创建时间'), displayDate(image.created_at, language)], [t('Image ID', '图像 ID'), image.id],
  ];
  return <dl className="grid grid-cols-[minmax(0,110px)_minmax(0,1fr)] gap-x-4 gap-y-2 text-xs">{data.map(([label, value]) => <div key={label} className="contents"><dt className="text-muted-foreground">{label}</dt><dd className="break-words">{value ?? t('Not recorded', '未记录')}</dd></div>)}</dl>;
}

function ImageInspector({ image, images, onSelect, refresh, maxUploadMb }: { image: FigureImage; images: FigureImage[]; onSelect: (id: string) => void; refresh: () => Promise<void>; maxUploadMb?: number }) {
  const { t } = useI18n();
  const preview = useImageBlob(image.id);
  const [zoom, setZoom] = useState(false);
  const ancestors = imageAncestors(image, images);
  return <div className="space-y-5">
    <ErrorNotice message={preview.error} />
    <div className="relative min-h-32 bg-muted/30">{preview.url ? <img src={preview.url} alt={t('Selected figure', '当前图像')} className="max-h-[55vh] w-full object-contain" /> : <Loading />}<div className="absolute bottom-2 right-2 bg-background"><IconButton label={t('Original size', '原始尺寸')} disabled={!preview.url} onClick={() => setZoom(true)}><Maximize2 className="h-4 w-4" /></IconButton></div></div>
    {image.parent_image_id && <div className="flex flex-wrap items-center gap-2 text-xs"><GitBranch className="h-4 w-4" /><span>{t('Ancestry', '版本来源')}:</span>{ancestors.length ? ancestors.map(parent => <button key={parent.id} type="button" className="text-primary underline" onClick={() => onSelect(parent.id)}>{parent.id.slice(0, 8)}</button>) : <span>{image.parent_image_id}</span>}<span>→ {image.id.slice(0, 8)}</span></div>}
    <Tabs defaultValue="details"><TabsList><TabsTrigger value="details">{t('Details', '详情')}</TabsTrigger><TabsTrigger value="edit">{t('Edit', '编辑')}</TabsTrigger><TabsTrigger value="provenance">{t('Provenance', '生成记录')}</TabsTrigger></TabsList>
      <TabsContent value="details"><ImageMetadata image={image} /></TabsContent>
      <TabsContent value="edit"><ImageEditor image={image} url={preview.url} refresh={refresh} maxUploadMb={maxUploadMb} /></TabsContent>
      <TabsContent value="provenance"><Provenance id={image.id} /></TabsContent>
    </Tabs>
    <Dialog open={zoom} onOpenChange={setZoom}><DialogContent className="max-w-[96vw]"><DialogHeader><DialogTitle>{t('Original size', '原始尺寸')}</DialogTitle><DialogDescription>{image.width_px} × {image.height_px}</DialogDescription></DialogHeader><div className="max-h-[75vh] overflow-auto"><img src={preview.url} alt={t('Original figure', '原始图像')} className="max-w-none" /></div></DialogContent></Dialog>
  </div>;
}

function Provenance({ id }: { id: string }) {
  const { t } = useI18n();
  const load = useCallback((signal: AbortSignal) => workbenchApi.provenance(id, signal), [id]);
  const resource = useResource(load, t('Could not load provenance.', '无法加载生成记录。'));
  return <div><ErrorNotice message={resource.error} />{resource.loading ? <Loading /> : <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{JSON.stringify(nonSecret(resource.data), null, 2)}</pre>}</div>;
}
