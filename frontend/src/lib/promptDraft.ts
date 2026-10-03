import type { FigureSpec } from './types';

export interface PromptSnapshot { text: string; spec: string; revision: number }
export interface PromptDraft { base: PromptSnapshot; text: string; spec: string }
const key = (id: string) => `workbench.promptDraft.${id}`;

export const figureSpecChanged = (base: string, draft: string) => base.trim() !== draft.trim();

export function figureSpecPatch(base: string, draft: string, spec?: FigureSpec): { figure_spec?: FigureSpec | null } {
  if (!figureSpecChanged(base, draft)) return {};
  if (!draft.trim()) return { figure_spec: null };
  if (!spec) throw new Error('Invalid FigureSpec');
  return { figure_spec: spec };
}

export function readPromptDraft(id: string, base: PromptSnapshot): PromptDraft {
  try {
    const saved = JSON.parse(sessionStorage.getItem(key(id)) ?? 'null') as PromptDraft | null;
    if (saved && typeof saved.text === 'string' && typeof saved.spec === 'string'
      && typeof saved.base?.text === 'string' && typeof saved.base?.spec === 'string'
      && Number.isInteger(saved.base?.revision) && saved.base.revision >= 1) return saved;
  } catch { /* Missing, unavailable, or invalid session storage starts from the saved revision. */ }
  return { base, text: base.text, spec: base.spec };
}

export function storePromptDraft(id: string, draft: PromptDraft) {
  try {
    if (draft.text === draft.base.text && draft.spec === draft.base.spec) sessionStorage.removeItem(key(id));
    else sessionStorage.setItem(key(id), JSON.stringify(draft));
  } catch { /* Keep the in-memory editor functional if storage is full or unavailable. */ }
}
