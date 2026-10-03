import type { Colors, ColorScheme, FigureImage, GenerationSettings, Job, Json, Prompt, Section } from './types';

export const DEFAULT_SETTINGS: GenerationSettings = {
  resolution: '2K', aspect_ratio: '16:9', color_scheme: 'okabe-ito', style_preset: 'classic', profile: 'quality',
};
export const activeStatus = (status: string) => ['queued', 'running', 'pending', 'generating', 'processing', 'parsing'].includes(status);
export const completedStatus = (status: string) => ['completed', 'succeeded'].includes(status);
export const canRetryJob = (job: Job) => job.status === 'failed' || job.status === 'interrupted';
export const promptText = (prompt: Prompt) => prompt.active_prompt ?? prompt.edited_prompt ?? prompt.original_prompt ?? '';
export const sectionIndex = (section: Section, position: number) => section.index ?? position;
export const newRequestKey = () => crypto.randomUUID();

export function findPalette(palettes: ColorScheme[], value: string): ColorScheme | undefined {
  const key = value.trim();
  if (!key) return undefined;
  const slug = key.replace(/^preset-/, '');
  return palettes.find(p => p.id === key)
    ?? palettes.find(p => p.slug === slug || p.id === `preset-${slug}`);
}

export function withPalette(settings: GenerationSettings, palettes: ColorScheme[]): GenerationSettings {
  const palette = findPalette(palettes, settings.color_scheme);
  return { ...settings, color_scheme: palette?.id || settings.color_scheme, custom_colors: settings.custom_colors ?? palette?.colors };
}

export function settingsForPrompt(prompt: Prompt, defaults: GenerationSettings): GenerationSettings {
  const metadata = prompt.generation_metadata ?? {};
  const palette = metadata.palette;
  const roles = ['primary', 'secondary', 'tertiary', 'text', 'fill', 'section_bg', 'border', 'arrow'];
  const validPalette = palette && typeof palette === 'object' && !Array.isArray(palette)
    && roles.every(role => typeof palette[role] === 'string' && /^#(?:[a-f\d]{3}|[a-f\d]{6})$/i.test(palette[role] as string));
  return {
    ...defaults,
    aspect_ratio: prompt.suggested_aspect_ratio || defaults.aspect_ratio,
    style_preset: prompt.style_preset ?? defaults.style_preset,
    profile: metadata.profile === 'draft' || metadata.profile === 'quality' ? metadata.profile : defaults.profile,
    color_scheme: typeof metadata.color_scheme === 'string' ? metadata.color_scheme : defaults.color_scheme,
    custom_colors: validPalette ? palette as unknown as Colors : defaults.custom_colors,
  };
}

export function imageAncestors(image: FigureImage, images: FigureImage[]): FigureImage[] {
  const chain: FigureImage[] = [];
  const seen = new Set([image.id]);
  let parent = image.parent_image_id;
  while (parent && !seen.has(parent)) {
    seen.add(parent);
    const next = images.find(item => item.id === parent);
    if (!next) break;
    chain.unshift(next);
    parent = next.parent_image_id;
  }
  return chain;
}

export function parseServerDate(value?: string | null): Date | null {
  if (typeof value !== 'string') return null;
  const parts = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:?\d{2})?)?$/i);
  if (!parts) return null;
  const [, year, month, day, hour = '00', minute = '00', second = '00', fraction = '', offset] = parts;
  const timestamp = `${year}-${month}-${day}T${hour}:${minute}:${second}.${fraction.slice(0, 3).padEnd(3, '0')}`;
  const calendarDate = new Date(`${timestamp}Z`);
  // Date normalizes some invalid calendar dates; reject them before applying the offset.
  if (!Number.isFinite(calendarDate.getTime()) || calendarDate.toISOString().slice(0, 19) !== timestamp.slice(0, 19)) return null;
  // SQLAlchemy's naive timestamps are UTC. Explicit offsets already identify the instant.
  const timezone = offset?.toUpperCase().replace(/([+-]\d{2})(\d{2})$/, '$1:$2') ?? 'Z';
  const date = new Date(`${timestamp}${timezone}`);
  return Number.isFinite(date.getTime()) ? date : null;
}

export function elapsed(start?: string | null, finish?: string | null): string {
  const startedAt = parseServerDate(start);
  const finishedAt = finish == null ? Date.now() : parseServerDate(finish)?.getTime();
  if (!startedAt || finishedAt == null) return '-';
  const ms = finishedAt - startedAt.getTime();
  if (!Number.isFinite(ms)) return '-';
  const seconds = Math.max(0, Math.round(ms / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

// Provenance is non-secret by contract. Exclude credentials even on older servers.
export function nonSecret(value: unknown): Json {
  if (value === null || typeof value === 'boolean' || typeof value === 'number') return value;
  if (typeof value === 'string') return value.replace(/\bsk-[\w-]+/gi, '[redacted]').replace(/Bearer\s+[\w.+/-]+/gi, 'Bearer [redacted]');
  if (Array.isArray(value)) return value.map(nonSecret);
  if (typeof value === 'object' && value) return Object.fromEntries(Object.entries(value)
    .filter(([key]) => !/(api.?key|secret|password|authorization|credential|access.?token|refresh.?token)/i.test(key))
    .map(([key, item]) => [key, nonSecret(item)]));
  return null;
}

export function displayDate(value: string | null | undefined, language: string): string {
  const date = parseServerDate(value);
  return date ? date.toLocaleString(language === 'zh' ? 'zh-CN' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : '-';
}
