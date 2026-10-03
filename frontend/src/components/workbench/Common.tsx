import { cloneElement, isValidElement, useId } from 'react';
import type { ComponentProps, ReactElement, ReactNode } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import { activeStatus, completedStatus } from '../../lib/workbench';
import { translateStatus, useI18n } from '../../lib/i18n';
import { redactText } from '../../lib/apiError';

export function IconButton({ label, children, ...props }: ComponentProps<typeof Button> & { label: string }) {
  return <TooltipProvider delayDuration={250}><Tooltip><TooltipTrigger asChild>
    <Button type="button" variant="ghost" size="icon" aria-label={label} {...props}>{children}</Button>
  </TooltipTrigger><TooltipContent>{label}</TooltipContent></Tooltip></TooltipProvider>;
}

export function ErrorNotice({ message, unknown = false, children }: { message?: string; unknown?: boolean; children?: ReactNode }) {
  const { t } = useI18n();
  if (!message) return null;
  return <div role="alert" className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
    <div className="min-w-0 flex-1 break-words"><p>{redactText(message)}</p>{unknown && <p className="mt-2 font-medium">{t('The outcome is unknown. Refresh jobs and history before starting another request; it may already be running.', '请求结果未知。再次提交前请刷新任务和历史，请求可能已在运行。')}</p>}{children}</div>
  </div>;
}

export function StatusBadge({ status }: { status: string }) {
  const { language } = useI18n();
  const color = activeStatus(status) ? 'text-blue-700 bg-blue-50' : completedStatus(status) ? 'text-emerald-700 bg-emerald-50' : ['failed', 'interrupted'].includes(status) ? 'text-red-700 bg-red-50' : 'text-muted-foreground bg-muted';
  return <span className={`inline-flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs ${color}`}>
    {activeStatus(status) && <Loader2 className="h-3 w-3 animate-spin" />}{translateStatus(status, language)}
  </span>;
}

export function Loading() {
  const { t } = useI18n();
  return <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />{t('Loading...', '加载中...')}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-sm text-muted-foreground">{children}</p>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return <div className="grid min-w-0 gap-1.5 text-sm"><label htmlFor={id} className="font-medium">{label}</label>{isValidElement(children) ? cloneElement(children as ReactElement<{ id: string }>, { id }) : children}</div>;
}
