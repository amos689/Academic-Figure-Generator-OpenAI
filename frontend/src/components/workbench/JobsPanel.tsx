import { Copy, Download, RotateCcw, X } from 'lucide-react';
import type { Job } from '../../lib/types';
import { workbenchApi } from '../../lib/api';
import { triggerBrowserDownload } from '../../lib/blob';
import { redactText } from '../../lib/apiError';
import { canRetryJob, displayDate, elapsed } from '../../lib/workbench';
import { translateStatus, useI18n } from '../../lib/i18n';
import { useAction } from '../../hooks/useAction';
import { Empty, ErrorNotice, IconButton, StatusBadge } from './Common';

export function JobsPanel({ jobs, refresh }: { jobs: Job[]; refresh: () => Promise<void> }) {
  const { t, language } = useI18n();
  const action = useAction();
  return <section aria-label={t('Jobs', '任务')} className="space-y-4">
    <ErrorNotice message={action.error} unknown={action.unknown} />
    {!jobs.length && <Empty>{t('No jobs', '暂无任务')}</Empty>}
    <ul className="divide-y">{jobs.map(job => <li key={job.id} className="space-y-2 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-medium">{translateStatus(job.kind, language)}</span><StatusBadge status={job.status} /><span className="text-xs text-muted-foreground">{elapsed(job.started_at, job.finished_at)}</span></div><p className="mt-2 break-words text-xs text-muted-foreground">{job.stage} · {displayDate(job.created_at, language)} · {job.id}</p></div>
        <div className="flex shrink-0 gap-1">{job.status === 'queued' && <IconButton label={t('Cancel queued job', '取消排队任务')} disabled={action.pending} onClick={() => void action.run(async () => { await workbenchApi.cancelJob(job.id); await refresh(); })}><X className="h-4 w-4" /></IconButton>}
          {canRetryJob(job) && <IconButton label={t('Retry as a new attempt', '重试为新任务')} disabled={action.pending} onClick={() => {
            if (!window.confirm(t('Start another attempt? Generation can incur a new charge. An interrupted request may already have reached the provider.', '开始新的尝试？生成可能产生新的费用，中断的请求可能已到达服务方。'))) return;
            void action.run(async () => { await workbenchApi.retryJob(job.id); await refresh(); }, true);
          }}><RotateCcw className="h-4 w-4" /></IconButton>}
        </div>
      </div>
      {job.retry_of && <p className="break-all text-xs text-muted-foreground">{t('Retry of', '重试来源')}: {job.retry_of}</p>}
      {job.status === 'running' && job.kind === 'image' && <p className="text-xs text-muted-foreground">{t('Running image requests cannot be cancelled.', '运行中的图像请求无法取消。')}</p>}
      <ErrorNotice message={job.error ?? ''} />
      {typeof job.result?.message === 'string' && <p className={`break-words text-sm ${job.result.applied === false ? 'text-amber-800' : 'text-muted-foreground'}`}>{redactText(job.result.message)}</p>}
      {job.result?.figure_spec && <div className="flex flex-wrap items-center gap-2 text-xs">
        <span>{job.result.applied === false ? t('Retained FigureSpec (not applied)', '保留的图形结构（未应用）') : 'FigureSpec'}</span>
        <IconButton label={t('Copy retained FigureSpec', '复制保留的图形结构')} disabled={action.pending} onClick={() => void action.run(async () => navigator.clipboard.writeText(JSON.stringify(job.result?.figure_spec, null, 2)))}><Copy className="h-4 w-4" /></IconButton>
        <IconButton label={t('Download retained FigureSpec', '下载保留的图形结构')} onClick={() => triggerBrowserDownload(new Blob([JSON.stringify(job.result?.figure_spec, null, 2)], { type: 'application/json' }), `figure-spec-${job.id}.json`)}><Download className="h-4 w-4" /></IconButton>
      </div>}
      {job.result && <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">{t('Result', '结果')}</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(job.result, null, 2)}</pre></details>}
    </li>)}</ul>
  </section>;
}
