import { useState } from 'react';
import { Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import type { Colors } from '../lib/types';
import { workbenchApi } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { useAction } from '../hooks/useAction';
import { useResource } from '../hooks/useResource';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Empty, ErrorNotice, Field, IconButton, Loading } from '../components/workbench/Common';

const initialColors: Colors = { primary: '#0072B2', secondary: '#E69F00', tertiary: '#009E73', text: '#333333', fill: '#FFFFFF', section_bg: '#F7F7F7', border: '#CCCCCC', arrow: '#4D4D4D' };

export function ColorSchemes() {
  const { t } = useI18n();
  const palettes = useResource(workbenchApi.palettes, t('Could not load palettes.', '无法加载配色。'));
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [colors, setColors] = useState(initialColors);
  const labels: Record<keyof Colors, string> = { primary: t('Primary', '主色'), secondary: t('Secondary', '辅助色'), tertiary: t('Tertiary', '第三色'), text: t('Text', '文字'), fill: t('Background', '背景'), section_bg: t('Section', '区域背景'), border: t('Border', '边框'), arrow: t('Arrow', '箭头') };
  return <div className="space-y-5"><header className="flex flex-wrap items-center justify-between gap-3 border-b pb-4"><h1 className="text-xl font-semibold">{t('Palettes', '配色')}</h1><div className="flex gap-2"><IconButton label={t('Refresh palettes', '刷新配色')} disabled={palettes.refreshing} onClick={() => void palettes.refresh()}><RefreshCw className="h-4 w-4" /></IconButton><Button onClick={() => { action.setError(''); setOpen(true); }}><Plus className="mr-2 h-4 w-4" />{t('New palette', '新建配色')}</Button></div></header>
    <ErrorNotice message={palettes.error || (!open ? action.error : '')} />{palettes.loading ? <Loading /> : !palettes.data?.length ? <Empty>{t('No palettes', '暂无配色')}</Empty> : <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">{palettes.data.map(palette => <article key={palette.id} className="min-w-0 rounded-md border p-4"><div className="flex items-start justify-between gap-2"><h2 className="break-words text-sm font-semibold">{palette.name}</h2>{palette.type !== 'preset' && <IconButton label={t(`Delete ${palette.name}`, `删除 ${palette.name}`)} disabled={action.pending} onClick={() => { if (window.confirm(t('Delete this palette?', '删除此配色？'))) void action.run(async () => { await workbenchApi.deletePalette(palette.id); await palettes.refresh(); }); }}><Trash2 className="h-4 w-4" /></IconButton>}</div><div className="mt-4 grid grid-cols-4 gap-3">{Object.entries(palette.colors).map(([key, color]) => <div key={key} className="min-w-0 text-center"><div style={{ backgroundColor: color }} title={color} className="mb-1 h-8 w-full rounded-sm border" /><span className="text-[11px] text-muted-foreground">{labels[key as keyof Colors]}</span></div>)}</div></article>)}</div>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>{t('New palette', '新建配色')}</DialogTitle><DialogDescription className="sr-only">{t('Palette colors', '配色颜色')}</DialogDescription></DialogHeader><form className="space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => { await workbenchApi.createPalette({ name: name.trim(), colors }); await palettes.refresh(); setName(''); setOpen(false); }); }}>
      <Field label={t('Name', '名称')}><Input value={name} onChange={e => setName(e.target.value)} required disabled={action.pending} /></Field>
      {Object.entries(colors).map(([key, color]) => <div key={key} className="grid grid-cols-[minmax(0,1fr)_48px_minmax(0,1fr)] items-center gap-3"><label htmlFor={`hex-${key}`} className="text-sm">{labels[key as keyof Colors]}</label><input type="color" aria-label={`${labels[key as keyof Colors]} ${t('swatch', '色块')}`} value={/^#[0-9a-fA-F]{6}$/.test(color) ? color : '#000000'} onChange={e => setColors(previous => ({ ...previous, [key]: e.target.value }))} className="h-9 w-12 cursor-pointer rounded-sm border" disabled={action.pending} /><Input id={`hex-${key}`} value={color} onChange={e => setColors(previous => ({ ...previous, [key]: e.target.value }))} required pattern="#[0-9a-fA-F]{6}" maxLength={7} className="font-mono text-xs" disabled={action.pending} /></div>)}
      <ErrorNotice message={action.error} /><Button type="submit" disabled={action.pending || !name.trim() || Object.values(colors).some(color => !/^#[0-9a-fA-F]{6}$/.test(color))}><Save className="mr-2 h-4 w-4" />{t('Save palette', '保存配色')}</Button>
    </form></DialogContent></Dialog>
  </div>;
}
