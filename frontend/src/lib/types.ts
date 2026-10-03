export type ID = string;
export type StylePreset = 'classic' | 'pastel';
export type Profile = 'quality' | 'draft';
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

export interface Colors {
  primary: string;
  secondary: string;
  tertiary: string;
  text: string;
  fill: string;
  section_bg: string;
  border: string;
  arrow: string;
}
export interface ColorScheme {
  id: ID;
  slug?: string | null;
  name: string;
  type: string;
  colors: Colors;
  is_default?: boolean;
}
export interface Project {
  id: ID;
  name: string;
  description: string | null;
  paper_field: string | null;
  color_scheme: string;
  custom_colors?: Colors | null;
  style_preset?: StylePreset;
  status: string;
  created_at: string;
  document_count: number;
  prompt_count: number;
  image_count: number;
}
export interface Section {
  index?: number;
  id?: string;
  title: string;
  level?: number;
  content?: string;
  text?: string;
  page_start?: number | null;
  page_end?: number | null;
  tables?: Json[];
}
export interface DocumentItem {
  id: ID;
  project_id: ID;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  page_count: number | null;
  parse_status: string;
  parse_error?: string | null;
  sections: Section[] | null;
  job_id?: ID | null;
  created_at: string;
}
export interface SourceReference { section_index: number; quote: string }
export interface FigureSpec {
  version: 1;
  title: string;
  caption: string;
  direction: 'LR' | 'TB';
  nodes: { id: string; label: string; role: 'input' | 'process' | 'output' | 'note'; group_id?: string | null; sources: SourceReference[] }[];
  edges: { id: string; source: string; target: string; label: string; kind: 'data' | 'control' | 'skip'; sources: SourceReference[] }[];
  groups: { id: string; label: string }[];
}
export interface Prompt {
  id: ID;
  project_id: ID;
  document_id: ID | null;
  figure_number: number;
  title: string | null;
  original_prompt: string | null;
  edited_prompt: string | null;
  active_prompt: string | null;
  suggested_figure_type: string | null;
  suggested_aspect_ratio: string | null;
  source_sections: Json;
  generation_status: string;
  generation_model?: string | null;
  claude_model?: string | null;
  revision: number;
  figure_spec: FigureSpec | null;
  style_preset?: StylePreset;
  generation_metadata?: Record<string, Json> | null;
  created_at: string;
}
export interface PromptRevision {
  id: ID;
  revision: number;
  prompt_text: string;
  figure_spec: FigureSpec | null;
  created_at: string;
}
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'interrupted' | 'cancelled';
export interface Job {
  id: ID;
  project_id: ID | null;
  kind: 'document' | 'prompt' | 'image' | 'spec' | 'export';
  status: JobStatus;
  stage: string | null;
  resource_id: ID | null;
  result: { prompt_ids?: ID[]; image_id?: ID; export_id?: ID; [key: string]: Json | undefined } | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  retry_of: ID | null;
}
export interface ImageStatus {
  id: ID;
  generation_status: string;
  generation_error?: string | null;
  job_id?: ID | null;
}
export interface FigureImage extends ImageStatus {
  project_id: ID | null;
  prompt_id: ID | null;
  parent_image_id?: ID | null;
  prompt_revision?: number | null;
  generation_model?: string | null;
  quality?: string | null;
  resolution: string;
  aspect_ratio: string;
  color_scheme: string | null;
  style_preset?: StylePreset;
  width_px: number | null;
  height_px: number | null;
  generation_duration_ms: number | null;
  generation_metadata?: Record<string, Json> | null;
  favorite?: boolean;
  selected?: boolean;
  created_at: string;
}
export type ExportFormat = 'svg' | 'pdf' | 'drawio';
export interface FigureExport {
  id: ID;
  prompt_id: ID;
  prompt_revision?: number;
  format: ExportFormat;
  created_at: string;
  generation_status: string;
  width_px: number | null;
  height_px: number | null;
  job_id: ID | null;
  generation_error: string | null;
  generation_metadata?: Record<string, Json> | null;
}
export interface Configuration {
  api_key_configured: boolean;
  api_key_source: string;
  api_base: string;
  text_model: string;
  text_reasoning_effort: string;
  text_max_output_tokens: number;
  image_model: string;
  image_quality: string;
  max_upload_size_mb: number;
  max_concurrent_jobs: number;
  styles: { id: StylePreset; name: string; description: string }[];
  profiles: { id: Profile; name: string; text_reasoning_effort: string; image_quality: string }[];
  usage_summary: { jobs_completed?: number | null; jobs_failed?: number | null; input_tokens?: number | null; output_tokens?: number | null; image_count?: number | null; duration_ms?: number | null };
}
export interface GenerationSettings {
  resolution: string;
  aspect_ratio: string;
  color_scheme: string;
  custom_colors?: Colors;
  style_preset: StylePreset;
  profile: Profile;
}
export interface PromptJobRequest {
  document_id: ID;
  section_indices: number[] | null;
  color_scheme: string;
  custom_colors?: Colors;
  figure_types: string[] | null;
  user_request: string;
  max_figures: number;
  template_mode: boolean;
  style_preset: StylePreset;
  profile: Profile;
  idempotency_key: string;
}
