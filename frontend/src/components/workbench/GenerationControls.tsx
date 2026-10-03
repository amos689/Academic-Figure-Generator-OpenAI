import type { ColorScheme, GenerationSettings } from '../../lib/types';
import { useI18n } from '../../lib/i18n';
import { findPalette } from '../../lib/workbench';
import { Field } from './Common';

export function GenerationControls({ value, onChange, palettes, image = true, disabled = false }: {
  value: GenerationSettings; onChange: (value: GenerationSettings) => void; palettes: ColorScheme[]; image?: boolean; disabled?: boolean;
}) {
  const { t } = useI18n();
  const update = (patch: Partial<GenerationSettings>) => onChange({ ...value, ...patch });
  const palette = findPalette(palettes, value.color_scheme);
  return <fieldset disabled={disabled} className="grid min-w-0 gap-3 sm:grid-cols-2">
    <Field label={t('Style', '风格')}><select value={value.style_preset} onChange={e => update({ style_preset: e.target.value as GenerationSettings['style_preset'] })}>
      <option value="classic">{t('Classic', '经典')}</option><option value="pastel">{t('Pastel', '柔和')}</option>
    </select></Field>
    <Field label={t('Profile', '生成档位')}><select value={value.profile} onChange={e => update({ profile: e.target.value as GenerationSettings['profile'] })}>
      <option value="quality">{t('Quality', '高质量')}</option><option value="draft">{t('Draft', '草稿')}</option>
    </select></Field>
    <div className="min-w-0 sm:col-span-2"><Field label={t('Palette', '配色')}>
      <select value={palette?.id || value.color_scheme} onChange={e => update({ color_scheme: e.target.value, custom_colors: findPalette(palettes, e.target.value)?.colors })}>
        {!palette && <option value={value.color_scheme}>{value.color_scheme}</option>}
        {palettes.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </Field><div className="mt-2 flex gap-1" aria-label={t('Palette colors', '配色预览')}>
      {Object.entries(palette?.colors ?? value.custom_colors ?? {}).map(([role, color]) => <span key={role} className="h-4 w-7 rounded-sm border" title={`${role}: ${color}`} style={{ backgroundColor: color }} />)}
    </div></div>
    {image && <><Field label={t('Resolution', '分辨率')}><select value={value.resolution} onChange={e => update({ resolution: e.target.value })}>
      {['1K', '2K', '4K'].map(v => <option key={v}>{v}</option>)}
    </select></Field><Field label={t('Aspect ratio', '宽高比')}><select value={value.aspect_ratio} onChange={e => update({ aspect_ratio: e.target.value })}>
      {['16:9', '4:3', '1:1', '3:4', '9:16', '3:2', '2:3', '21:9', '9:21', '1:2', ...(!['16:9', '4:3', '1:1', '3:4', '9:16', '3:2', '2:3', '21:9', '9:21', '1:2'].includes(value.aspect_ratio) ? [value.aspect_ratio] : [])].map(v => <option key={v}>{v}</option>)}
    </select></Field></>}
  </fieldset>;
}
