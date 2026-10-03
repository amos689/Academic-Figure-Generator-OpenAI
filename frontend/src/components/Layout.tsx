import { useEffect, useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { FolderOpen, Menu, Palette, Settings, Zap } from 'lucide-react';
import { useI18n, useLanguage } from '../lib/i18n';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';

const links = [
  { en: 'Projects', zh: '项目', path: '/projects', icon: FolderOpen },
  { en: 'Direct generation', zh: '直接生成', path: '/generate', icon: Zap },
  { en: 'Palettes', zh: '配色', path: '/color-schemes', icon: Palette },
  { en: 'Settings', zh: '设置', path: '/settings', icon: Settings },
];

function Navigation({ close }: { close?: () => void }) {
  const { t } = useI18n();
  const { pathname } = useLocation();
  return <nav aria-label={t('Main navigation', '主导航')} className="space-y-1">{links.map(item => <Link key={item.path} to={item.path} onClick={close} aria-current={pathname.startsWith(item.path) ? 'page' : undefined} className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm ${pathname.startsWith(item.path) ? 'bg-background font-medium text-foreground shadow-sm' : 'text-muted-foreground hover:bg-background hover:text-foreground'}`}><item.icon className="h-4 w-4 shrink-0" /><span>{t(item.en, item.zh)}</span></Link>)}</nav>;
}

function LanguageSwitch() {
  const { language, setLanguage } = useLanguage();
  return <div role="group" aria-label={language === 'en' ? 'Language' : '语言'} className="inline-flex rounded-md border bg-background p-0.5">
    <button type="button" lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')} className={`min-h-8 min-w-10 rounded px-2 text-xs ${language === 'en' ? 'bg-muted font-semibold' : 'text-muted-foreground'}`}>EN</button>
    <button type="button" lang="zh" aria-pressed={language === 'zh'} onClick={() => setLanguage('zh')} className={`min-h-8 min-w-10 rounded px-2 text-xs ${language === 'zh' ? 'bg-muted font-semibold' : 'text-muted-foreground'}`}>中文</button>
  </div>;
}

export default function Layout() {
  const { t, language } = useI18n();
  const [open, setOpen] = useState(false);
  useEffect(() => { document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'; document.title = t('Academic Figure Workbench', '科研配图工作台'); }, [language, t]);
  return <div className="min-h-screen bg-background">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:bg-background focus:p-3">{t('Skip to content', '跳转到内容')}</a>
    <aside className="fixed inset-y-0 left-0 hidden w-52 flex-col border-r bg-muted/60 p-3 md:flex"><Link to="/projects" className="mb-7 flex items-center gap-2 px-1 pt-3"><img src="/logo.png" alt="" className="h-8 w-8 object-contain" /><span className="text-sm font-semibold">{t('Figure Workbench', '科研配图工作台')}</span></Link><Navigation /><div className="mt-auto border-t pt-4"><LanguageSwitch /></div></aside>
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-2 border-b bg-background px-3 md:hidden"><div className="flex min-w-0 items-center gap-2"><Button variant="ghost" size="icon" aria-label={t('Open navigation', '打开导航')} onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></Button><span className="text-sm font-semibold">{t('Figure Workbench', '科研配图工作台')}</span></div><LanguageSwitch /></header>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-sm"><DialogHeader><DialogTitle>{t('Figure Workbench', '科研配图工作台')}</DialogTitle><DialogDescription className="sr-only">{t('Navigation', '导航')}</DialogDescription></DialogHeader><Navigation close={() => setOpen(false)} /></DialogContent></Dialog>
    <main id="main-content" className="min-w-0 px-4 py-5 md:ml-52 md:px-6 lg:px-8"><Outlet /></main>
  </div>;
}
