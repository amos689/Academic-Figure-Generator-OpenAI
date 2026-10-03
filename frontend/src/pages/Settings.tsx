import { useState } from 'react';
import { RefreshCw, ShieldCheck } from 'lucide-react';
import type { Json } from '../lib/types';
import { workbenchApi } from '../lib/api';
import { nonSecret } from '../lib/workbench';
import { useI18n } from '../lib/i18n';
import { useResource } from '../hooks/useResource';
import { useAction } from '../hooks/useAction';
import { Button } from '../components/ui/button';
import { ErrorNotice, IconButton, Loading } from '../components/workbench/Common';

export function Settings() {
  const { t } = useI18n();
  const configuration = useResource(workbenchApi.configuration, t('Could not load effective settings.', '无法加载有效配置。'));
  const action = useAction();
  const [check, setCheck] = useState<Record<string, Json>>();
  const config = configuration.data;
  const settings = config ? [
    [t('API key', 'API 密钥'), config.api_key_configured ? t('Configured', '已配置') : t('Not configured', '未配置')],
    [t('Key source', '密钥来源'), config.api_key_source], [t('API base', 'API 地址'), config.api_base],
    [t('Text model', '文本模型'), config.text_model], [t('Reasoning effort', '推理强度'), config.text_reasoning_effort],
    [t('Maximum output tokens', '最大输出 Token'), config.text_max_output_tokens], [t('Image model', '图像模型'), config.image_model],
    [t('Image quality', '图像质量'), config.image_quality], [t('Upload limit (MB)', '上传限制（MB）'), config.max_upload_size_mb],
    [t('Concurrent jobs', '并发任务数'), config.max_concurrent_jobs],
  ] : [];
  const usageLabels = { jobs_completed: t('Completed jobs', '完成任务'), jobs_failed: t('Failed jobs', '失败任务'), input_tokens: t('Input tokens', '输入 Token'), output_tokens: t('Output tokens', '输出 Token'), image_count: t('Images', '图像'), duration_ms: t('Duration (ms)', '耗时（毫秒）') };
  return <div className="max-w-4xl space-y-6"><header className="flex items-center justify-between border-b pb-4"><h1 className="text-xl font-semibold">{t('Effective settings', '有效配置')}</h1><IconButton label={t('Refresh settings', '刷新配置')} disabled={configuration.refreshing} onClick={() => void configuration.refresh()}><RefreshCw className="h-4 w-4" /></IconButton></header>
    <ErrorNotice message={configuration.error || action.error} />{configuration.loading && <Loading />}
    {config && <><dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-x-4 text-sm">{settings.map(([label, value]) => <div key={label} className="contents"><dt className="border-b py-3 text-muted-foreground">{label}</dt><dd className="break-words border-b py-3 font-medium">{String(nonSecret(value) ?? t('Unknown', '未知'))}</dd></div>)}</dl>
      <Button variant="outline" disabled={action.pending} onClick={() => void action.run(async () => setCheck(await workbenchApi.checkConfiguration()))}><ShieldCheck className="mr-2 h-4 w-4" />{t('Check connectivity & model access', '检查连接与模型访问')}</Button>
      {check && <pre role="status" className="overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{JSON.stringify(nonSecret(check), null, 2)}</pre>}
      <section className="space-y-3 border-t pt-5"><h2 className="text-base font-semibold">{t('Usage', '用量')}</h2><dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">{Object.entries(usageLabels).map(([key, label]) => <div key={key}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-lg font-medium">{config.usage_summary?.[key as keyof typeof config.usage_summary]?.toLocaleString() ?? t('Unknown', '未知')}</dd></div>)}</dl></section>
      <section className="space-y-3 border-t pt-5"><h2 className="text-base font-semibold">{t('Profiles', '生成档位')}</h2><ul className="divide-y">{config.profiles.map(profile => <li key={profile.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><span>{profile.name}</span><span className="text-muted-foreground">{profile.text_reasoning_effort} · {profile.image_quality}</span></li>)}</ul></section>
      <section className="space-y-3 border-t pt-5"><h2 className="text-base font-semibold">{t('Styles', '风格')}</h2><ul className="divide-y">{config.styles.map(style => <li key={style.id} className="py-3 text-sm"><span className="font-medium">{style.name}</span><p className="mt-1 text-muted-foreground">{style.description}</p></li>)}</ul></section>
    </>}
  </div>;
}
