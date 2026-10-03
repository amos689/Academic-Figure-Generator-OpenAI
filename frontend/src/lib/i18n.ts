import { create } from 'zustand';

export type Language = 'en' | 'zh';
const initialLanguage = (): Language => {
  try { return localStorage.getItem('workbench.language') === 'zh' ? 'zh' : 'en'; } catch { return 'en'; }
};
export const useLanguage = create<{ language: Language; setLanguage: (language: Language) => void }>((set) => ({
  language: initialLanguage(),
  setLanguage: (language) => {
    try { localStorage.setItem('workbench.language', language); } catch { /* Session-only preference. */ }
    set({ language });
  },
}));

export function useI18n() {
  const language = useLanguage(state => state.language);
  return { language, t: (en: string, zh: string) => language === 'zh' ? zh : en };
}

const statuses: Record<string, [string, string]> = {
  queued: ['Queued', '排队中'], running: ['Running', '运行中'], pending: ['Pending', '待处理'],
  generating: ['Generating', '生成中'], processing: ['Processing', '处理中'], parsing: ['Parsing', '解析中'],
  completed: ['Completed', '已完成'], succeeded: ['Succeeded', '已完成'], failed: ['Failed', '失败'],
  interrupted: ['Interrupted', '已中断'], cancelled: ['Cancelled', '已取消'],
  document: ['Document', '文档'], prompt: ['Prompt', '提示词'], image: ['Image', '图像'],
  spec: ['FigureSpec', '图形结构'], export: ['Export', '导出'],
};
export const translateStatus = (value: string, language: Language) => statuses[value]?.[language === 'zh' ? 1 : 0] ?? value;
