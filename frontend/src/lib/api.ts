import axios from "axios";
import type { ColorScheme, Configuration, DocumentItem, FigureExport, FigureImage, FigureSpec, GenerationSettings, ImageStatus, Job, Project, Prompt, PromptJobRequest, PromptRevision, ExportFormat, Json } from './types';

const api = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || "/api/v1",
  timeout: 30000,
});

export default api;

const path = (id: string) => encodeURIComponent(id);
const get = async <T>(url: string, signal?: AbortSignal): Promise<T> => (await api.get<T>(url, { signal })).data;
const post = async <T>(url: string, data?: unknown): Promise<T> => (await api.post<T>(url, data)).data;

export const workbenchApi = {
  projects: (signal?: AbortSignal) => get<{ items: Project[]; total: number }>('/projects/?page=1&page_size=100&status=active', signal),
  project: (id: string, signal?: AbortSignal) => get<Project>(`/projects/${path(id)}`, signal),
  createProject: (data: Pick<Project, 'name' | 'description' | 'paper_field' | 'color_scheme'>) => post<Project>('/projects/', data),
  updateProject: async (id: string, data: Partial<Pick<Project, 'name' | 'description' | 'color_scheme' | 'custom_colors' | 'style_preset'>>) => (await api.put<Project>(`/projects/${path(id)}`, data)).data,
  deleteProject: (id: string) => api.delete(`/projects/${path(id)}`),
  documents: (id: string, signal?: AbortSignal) => get<DocumentItem[]>(`/projects/${path(id)}/documents`, signal),
  uploadDocument: async (id: string, file: File, progress: (percent: number) => void) => {
    const body = new FormData();
    body.append('file', file);
    return (await api.post<DocumentItem>(`/projects/${path(id)}/documents`, body, {
      timeout: 120000,
      onUploadProgress: ({ loaded, total }) => progress(total ? Math.round(loaded / total * 100) : 0),
    })).data;
  },
  prompts: (id: string, signal?: AbortSignal) => get<Prompt[]>(`/projects/${path(id)}/prompts`, signal),
  promptJob: (id: string, data: PromptJobRequest) => post<Job>(`/projects/${path(id)}/prompt-jobs`, data),
  savePrompt: async (id: string, data: { edited_prompt: string; expected_revision: number; figure_spec?: FigureSpec | null }) => (await api.put<Prompt>(`/prompts/${path(id)}`, data)).data,
  revisions: (id: string, signal?: AbortSignal) => get<PromptRevision[]>(`/prompts/${path(id)}/revisions`, signal),
  restorePrompt: (id: string, revision: number, expected_revision?: number) => post<Prompt>(`/prompts/${path(id)}/restore`, { revision, expected_revision }),
  specJob: (id: string, idempotency_key: string) => post<Job>(`/prompts/${path(id)}/spec-jobs`, { idempotency_key }),
  images: (id: string, signal?: AbortSignal) => get<FigureImage[]>(`/projects/${path(id)}/images`, signal),
  image: (id: string, signal?: AbortSignal) => get<FigureImage>(`/images/${path(id)}`, signal),
  imageJob: (id: string, data: GenerationSettings & { idempotency_key: string }) => post<ImageStatus>(`/prompts/${path(id)}/images/generate`, data),
  directImage: (data: GenerationSettings & { prompt: string; project_id?: string; idempotency_key: string }) => post<ImageStatus>('/images/generate-direct', data),
  editImage: (id: string, data: { instruction: string; reference?: File; mask?: Blob; idempotencyKey: string }) => {
    const body = new FormData();
    body.append('edit_instruction', data.instruction);
    body.append('idempotency_key', data.idempotencyKey);
    if (data.reference) body.append('reference_image', data.reference);
    if (data.mask) body.append('mask_image', data.mask, 'mask.png');
    return post<ImageStatus>(`/images/${path(id)}/edit`, body);
  },
  updateImage: async (id: string, data: { favorite?: boolean; selected?: boolean }) => (await api.patch<FigureImage>(`/images/${path(id)}`, data)).data,
  provenance: (id: string, signal?: AbortSignal) => get<Record<string, Json>>(`/images/${path(id)}/provenance`, signal),
  jobs: (id?: string, signal?: AbortSignal) => get<Job[]>(`/jobs${id ? `?project_id=${path(id)}` : ''}`, signal),
  job: (id: string, signal?: AbortSignal) => get<Job>(`/jobs/${path(id)}`, signal),
  cancelJob: (id: string) => post<Job>(`/jobs/${path(id)}/cancel`),
  retryJob: (id: string) => post<Job>(`/jobs/${path(id)}/retry`),
  exports: (id: string, signal?: AbortSignal) => get<FigureExport[]>(`/projects/${path(id)}/exports`, signal),
  exportFigure: (id: string, data: { format: ExportFormat; figure_spec?: FigureSpec; width: number; idempotency_key: string }) => post<Job>(`/prompts/${path(id)}/exports`, data),
  palettes: (signal?: AbortSignal) => get<ColorScheme[]>('/color-schemes/', signal),
  createPalette: (data: Pick<ColorScheme, 'name' | 'colors'>) => post<ColorScheme>('/color-schemes/', data),
  deletePalette: (id: string) => api.delete(`/color-schemes/${path(id)}`),
  configuration: (signal?: AbortSignal) => get<Configuration>('/configuration', signal),
  checkConfiguration: () => post<Record<string, Json>>('/configuration/check'),
  styles: (signal?: AbortSignal) => get<Configuration['styles']>('/styles', signal),
};
