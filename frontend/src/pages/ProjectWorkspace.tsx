import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileUp, FileText, Image as ImageIcon, Send, RefreshCw, Download, ChevronLeft, ChevronRight, ScanText, FileDown, AlertCircle, CheckCircle2, Loader2, Eye } from 'lucide-react';

import api from '../lib/api';
import { useProjectStore } from '../store/projectStore';
import { fetchAuthedBlob, triggerBrowserDownload } from '../lib/blob';
import { getApiErrorMessage } from '../lib/apiError';

import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

type DocumentItem = {
    id: string;
    original_filename: string;
    file_type: string;
    file_size_bytes: number;
    page_count?: number | null;
    parse_status: 'pending' | 'parsing' | 'completed' | 'failed' | string;
    parse_error?: string | null;
    ocr_markdown?: string | null;
    sections?: Array<{
        title?: string;
        content?: string;
        text?: string;
        level?: number;
        page_start?: number | null;
        page_end?: number | null;
    }> | null;
    created_at?: string;
};

type PromptSettings = {
    resolution: string;
    aspectRatio: string;
    colorScheme: string;
};

const IMAGE_IN_PROGRESS_STATUSES = new Set(['pending', 'generating', 'processing']);

export function ProjectWorkspace() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { currentProject, setCurrentProject } = useProjectStore();

    const [isInitialLoading, setIsInitialLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [documents, setDocuments] = useState<DocumentItem[]>([]);
    const [prompts, setPrompts] = useState<any[]>([]);
    const [images, setImages] = useState<any[]>([]);

    // Upload state
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);

    // Generation state
    const [isAutoGenerating, setIsAutoGenerating] = useState(false);
    const [isDownloading, setIsDownloading] = useState<string | null>(null);
    const [isPreviewing, setIsPreviewing] = useState<Record<string, boolean>>({});
    const [imagePreviews, setImagePreviews] = useState<Record<string, string>>({});
    const previewUrlsRef = useRef<Record<string, string>>({});
    const [promptMode, setPromptMode] = useState<'overall' | 'sections'>('overall');
    const [promptRequest, setPromptRequest] = useState('');
    const [templateMode, setTemplateMode] = useState(false);
    const [selectedSectionIndices, setSelectedSectionIndices] = useState<number[]>([]);
    const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
    const [showStructure, setShowStructure] = useState(true);
    const [showDocs, setShowDocs] = useState(true);
    const structureInitRef = useRef<string | null>(null);
    const [ocrLoading, setOcrLoading] = useState<Record<string, boolean>>({});
    const [activePreviewIdx, setActivePreviewIdx] = useState<number | null>(null);

    type SectionNode = {
        idx: number;
        title: string;
        level: number;
        preview: string;
        children: SectionNode[];
    };

    const inferLevelFromTitle = (rawTitle: string): number | null => {
        const title = rawTitle.trim();
        if (!title) return null;

        if (/^第\s*[0-9一二三四五六七八九十百千]+\s*章\b/.test(title)) return 1;
        if (/^chapter\s+\d+\b/i.test(title)) return 1;

        const dotted = title.match(/^(\d+(?:\.\d+)+)\b/);
        if (dotted) return dotted[1].split('.').length;

        const leadingNum = title.match(/^(\d+)\b/);
        if (leadingNum) return 1;

        return null;
    };

    const buildSectionTree = (sections: DocumentItem['sections']): SectionNode[] => {
        const arr = (sections || []).map((sec, idx) => {
            const title = (sec?.title || `Section ${idx + 1}`).toString();
            const rawLevel = Number(sec?.level) || 1;
            const previewText = (sec?.content || sec?.text || '').toString().trim();
            const inferred = inferLevelFromTitle(title);
            return { idx, title, rawLevel, inferred, preview: previewText };
        });

        const rawLevels = arr.map((s) => s.rawLevel);
        const rawVaries = new Set(rawLevels).size > 1;
        const inferredLevels = arr.map((s) => s.inferred).filter((x): x is number => typeof x === 'number');
        const inferredVaries = new Set(inferredLevels).size > 1;
        const useInferred = !rawVaries && inferredVaries;

        const nodes: SectionNode[] = arr.map((s) => ({
            idx: s.idx,
            title: s.title,
            level: useInferred ? (s.inferred || s.rawLevel) : s.rawLevel,
            preview: s.preview,
            children: [],
        }));

        const roots: SectionNode[] = [];
        const stack: SectionNode[] = [];
        for (const node of nodes) {
            const level = Math.max(1, Math.floor(node.level || 1));
            node.level = level;
            while (stack.length && level <= stack[stack.length - 1].level) stack.pop();
            if (!stack.length) roots.push(node);
            else stack[stack.length - 1].children.push(node);
            stack.push(node);
        }

        return roots;
    };

    const collectIndices = (node: SectionNode): number[] => {
        const out: number[] = [node.idx];
        const stack: SectionNode[] = [...node.children];
        while (stack.length) {
            const cur = stack.pop()!;
            out.push(cur.idx);
            for (const ch of cur.children) stack.push(ch);
        }
        return out;
    };

    // Per-image features
    const [colorSchemes, setColorSchemes] = useState<any[]>([]);
    const [editInstructions, setEditInstructions] = useState<Record<string, string>>({});
    const [isEditing, setIsEditing] = useState<Record<string, boolean>>({});
    const [promptSettings, setPromptSettings] = useState<Record<string, PromptSettings>>({});

    const getSettings = (promptId: string): PromptSettings => {
        if (promptSettings[promptId]) return promptSettings[promptId];
        const prompt = prompts.find(p => p.id === promptId);
        return {
            resolution: '2K',
            aspectRatio: prompt?.suggested_aspect_ratio || '16:9',
            colorScheme: currentProject?.color_scheme || 'okabe-ito',
        };
    };

    const updateSetting = (promptId: string, field: keyof PromptSettings, value: string) => {
        setPromptSettings(prev => ({
            ...prev,
            [promptId]: {
                ...(prev[promptId] || getSettings(promptId)),
                [field]: value,
            },
        }));
    };

    useEffect(() => {
        if (id) {
            fetchProjectData(id, { showLoader: true });
        }
        return () => setCurrentProject(null);
    }, [id]);

    useEffect(() => {
        const parsedDoc = documents.find(
            (d) => d.parse_status === 'completed' && Array.isArray(d.sections) && d.sections.length > 0
        );
        if (!parsedDoc?.id || !Array.isArray(parsedDoc.sections) || parsedDoc.sections.length === 0) return;
        if (structureInitRef.current === parsedDoc.id) return;

        const roots = buildSectionTree(parsedDoc.sections);
        const next: Record<string, boolean> = {};
        for (const r of roots) next[`sec-${r.idx}`] = true; // default collapsed: only show chapters
        setCollapsedGroups(next);
        structureInitRef.current = parsedDoc.id;
    }, [documents]);

    useEffect(() => {
        return () => {
            for (const url of Object.values(previewUrlsRef.current)) {
                try { URL.revokeObjectURL(url); } catch { /* ignore */ }
            }
            previewUrlsRef.current = {};
        };
    }, []);

    // Poll while any image is still in progress
    useEffect(() => {
        const hasProcessing = images.some(img => IMAGE_IN_PROGRESS_STATUSES.has(img.generation_status));
        if (!hasProcessing || !id) return;
        const interval = setInterval(() => { fetchProjectData(id, { showLoader: false }); }, 5000);
        return () => clearInterval(interval);
    }, [images, id]);

    // Poll while any document is still parsing (including OCR)
    useEffect(() => {
        const hasParsing = documents.some(d => d.parse_status === 'parsing' || d.parse_status === 'pending');
        if (!hasParsing || !id) return;
        const interval = setInterval(() => { fetchProjectData(id, { showLoader: false }); }, 4000);
        return () => clearInterval(interval);
    }, [documents, id]);

    const fetchProjectData = async (projectId: string, opts?: { showLoader?: boolean }) => {
        const showLoader = opts?.showLoader ?? false;
        if (showLoader) setIsInitialLoading(true);
        else setIsRefreshing(true);
        try {
            const projRes = await api.get(`/projects/${projectId}`);
            setCurrentProject(projRes.data);

            try {
                const docsRes = await api.get(`/projects/${projectId}/documents`);
                const nextDocs = docsRes.data || [];
                setDocuments(nextDocs);
                const firstParsed = nextDocs.find(
                    (d: any) => d.parse_status === 'completed' && Array.isArray(d.sections) && d.sections.length > 0
                );
                if (firstParsed?.sections?.length && selectedSectionIndices.length === 0) {
                    setSelectedSectionIndices(firstParsed.sections.map((_: any, idx: number) => idx));
                }
            } catch (e) {
                console.debug('Failed to fetch documents', e);
                setDocuments([]);
            }

            try {
                const promptsRes = await api.get(`/projects/${projectId}/prompts`);
                setPrompts(promptsRes.data);
            } catch (e) {
                console.debug('Failed to fetch prompts', e);
            }

            try {
                const imagesRes = await api.get(`/projects/${projectId}/images`);
                setImages(imagesRes.data);
            } catch (e) {
                console.debug('Failed to fetch images', e);
            }

            try {
                const schemesRes = await api.get('/color-schemes/');
                setColorSchemes(schemesRes.data || []);
            } catch (e) {
                console.debug('Failed to fetch color schemes', e);
            }


        } catch (err) {
            console.error(err);
            navigate('/projects');
        } finally {
            if (showLoader) setIsInitialLoading(false);
            else setIsRefreshing(false);
        }
    };

    const ensureImagePreview = useCallback(async (imageId: string) => {
        if (imagePreviews[imageId]) return;
        if (isPreviewing[imageId]) return;

        setIsPreviewing(prev => ({ ...prev, [imageId]: true }));
        try {
            const { blob } = await fetchAuthedBlob(`/images/${imageId}/download`);
            const url = URL.createObjectURL(blob);

            const old = previewUrlsRef.current[imageId];
            if (old) { try { URL.revokeObjectURL(old); } catch { /* ignore */ } }
            previewUrlsRef.current[imageId] = url;
            setImagePreviews(prev => ({ ...prev, [imageId]: url }));
        } catch (err) {
            console.error('Preview fetch failed', err);
        } finally {
            setIsPreviewing(prev => ({ ...prev, [imageId]: false }));
        }
    }, [imagePreviews, isPreviewing]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !id) return;

        setIsUploading(true);
        setUploadProgress(0);
        const formData = new FormData();
        formData.append('file', file);

        try {
            await api.post(`/projects/${id}/documents`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (evt) => {
                    const total = evt.total || 0;
                    if (!total) return;
                    setUploadProgress(Math.min(100, Math.round((evt.loaded / total) * 100)));
                },
            });
            await fetchProjectData(id);
            alert('文件上传成功，已加入解析队列。');
        } catch (err: any) {
            console.error('File upload failed', err);
            const detail = err?.response?.data?.detail;
            alert(detail ? `文件上传失败：${detail}` : '文件上传失败，请检查后端/存储服务是否正常。');
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleTriggerOcr = async (doc: DocumentItem) => {
        if (!id || ocrLoading[doc.id]) return;
        setOcrLoading(prev => ({ ...prev, [doc.id]: true }));
        try {
            await api.post(`/projects/${id}/documents/${doc.id}/ocr`);
            // Poll until parse_status changes from 'parsing'
            const deadline = Date.now() + 300_000;
            while (Date.now() < deadline) {
                await new Promise(r => setTimeout(r, 3000));
                const docsRes = await api.get(`/projects/${id}/documents`);
                const updated = (docsRes.data || []).find((d: DocumentItem) => d.id === doc.id);
                setDocuments(docsRes.data || []);
                if (updated && updated.parse_status !== 'parsing') break;
            }
            await fetchProjectData(id, { showLoader: false });
        } catch (err: any) {
            alert(`OCR 解析触发失败：${getApiErrorMessage(err, '请检查 PaddleOCR 配置。')}`);
        } finally {
            setOcrLoading(prev => ({ ...prev, [doc.id]: false }));
        }
    };

    const handleDownloadMarkdown = (doc: DocumentItem) => {
        if (!doc.ocr_markdown) return;
        const blob = new Blob([doc.ocr_markdown], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.original_filename.replace(/\.[^/.]+$/, '') + '_ocr.md';
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleDownloadImage = async (imageId: string) => {
        try {
            setIsDownloading(imageId);
            const { blob, ext } = await fetchAuthedBlob(`/images/${imageId}/download`);
            triggerBrowserDownload(blob, `academic-figure-${imageId}.${ext}`);
        } catch (err: any) {
            console.error('Download failed', err);
            const detail = err?.response?.data?.detail;
            alert(detail ? `下载失败：${detail}` : '下载失败，请稍后重试。');
        } finally {
            setIsDownloading(null);
        }
    };

    /** Generate prompts then auto-trigger image generation for each new prompt */
    const handleAutoGenerate = async () => {
        if (!id) return;

        const parsedDoc = documents.find((d) => d.parse_status === 'completed' && Array.isArray(d.sections) && d.sections.length > 0);
        if (!parsedDoc) {
            alert('请先上传文档并等待解析完成，再生成配图。');
            return;
        }

        if (promptMode === 'sections' && selectedSectionIndices.length === 0) {
            alert('请至少选择一个章节。');
            return;
        }

        setIsAutoGenerating(true);
        try {
            const beforeCount = prompts.length;
            const payload: any = {
                section_indices: selectedSectionIndices.length ? selectedSectionIndices : null,
                color_scheme: currentProject?.color_scheme || 'okabe-ito',
                figure_types: promptMode === 'overall' ? ['overall_framework'] : null,
                user_request: templateMode ? null : (promptRequest.trim() ? promptRequest.trim() : null),
                max_figures: promptMode === 'overall' ? 1 : null,
                template_mode: templateMode,
            };

            await api.post(`/projects/${id}/prompts/generate`, payload);

            // Poll until new prompts appear
            let newPrompts: any[] = [];
            const deadline = Date.now() + 90_000;
            while (Date.now() < deadline) {
                await new Promise((r) => setTimeout(r, 2000));
                const promptsRes = await api.get(`/projects/${id}/prompts`);
                const next = promptsRes.data || [];
                setPrompts(next);
                if (next.length > beforeCount) {
                    newPrompts = next.slice(beforeCount);
                    break;
                }
            }

            // Initialize per-prompt default settings so selectors have values
            for (const prompt of newPrompts) {
                const aspectRatio = prompt.suggested_aspect_ratio || '16:9';
                const cs = currentProject?.color_scheme || 'okabe-ito';
                setPromptSettings(prev => ({
                    ...prev,
                    [prompt.id]: { resolution: '2K', aspectRatio, colorScheme: cs },
                }));
            }

            // Refresh to pick up image records
            await fetchProjectData(id, { showLoader: false });
        } catch (err: any) {
            console.error('Failed to auto-generate', err);
            alert(`生成配图失败：${getApiErrorMessage(err, '请稍后重试。')}`);
        } finally {
            setIsAutoGenerating(false);
        }
    };

    /** Generate (or re-generate) an image for a single prompt using its current settings */
    const handleGenerateImage = async (promptId: string) => {
        if (!id) return;
        const settings = getSettings(promptId);
        try {
            await api.post(`/prompts/${promptId}/images/generate`, {
                resolution: settings.resolution,
                aspect_ratio: settings.aspectRatio,
                color_scheme: settings.colorScheme,
            });
            await fetchProjectData(id, { showLoader: false });
        } catch (err: any) {
            console.error('Failed to generate image', err);
            const msg = getApiErrorMessage(err, '生成图片失败，请稍后重试。');
            alert(`生成图片失败：${msg}`);
        }
    };

    /** Edit an existing image with a text instruction (image-to-image) */
    const handleEditImage = async (imageId: string) => {
        const instruction = editInstructions[imageId]?.trim();
        if (!instruction || !id) return;

        setIsEditing(prev => ({ ...prev, [imageId]: true }));
        try {
            const formData = new FormData();
            formData.append('edit_instruction', instruction);
            await api.post(`/images/${imageId}/edit`, formData);
            setEditInstructions(prev => ({ ...prev, [imageId]: '' }));
            await fetchProjectData(id, { showLoader: false });
        } catch (err: any) {
            console.error('Edit image failed', err);
            alert(`改图失败：${getApiErrorMessage(err, '请稍后重试。')}`);
        } finally {
            setIsEditing(prev => ({ ...prev, [imageId]: false }));
        }
    };

    if (isInitialLoading && !currentProject) return <div className="p-8">加载中...</div>;
    if (!currentProject) return <div className="p-8">找不到该项目...</div>;

    const renderParsedStructure = () => {
        const parsedDoc = documents.find((d) => d.parse_status === 'completed' && Array.isArray(d.sections) && d.sections.length > 0);

        // Show loading/error states for any document being parsed
        const parsingDoc = documents.find((d) => d.parse_status === 'parsing' || d.parse_status === 'pending');
        const failedDoc = documents.find((d) => d.parse_status === 'failed');

        if (!parsedDoc) {
            return (
                <div className="space-y-3 py-2">
                    {parsingDoc && (
                        <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-700 text-sm">
                            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                            <span>正在解析 <strong>{parsingDoc.original_filename}</strong>，请稍候…</span>
                        </div>
                    )}
                    {failedDoc && (
                        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                            <div>
                                <p className="font-medium">解析失败：{failedDoc.original_filename}</p>
                                {failedDoc.parse_error && <p className="text-xs mt-1 opacity-80">{failedDoc.parse_error}</p>}
                            </div>
                        </div>
                    )}
                    {!parsingDoc && !failedDoc && (
                        <div className="text-sm text-muted-foreground py-4 text-center">上传文档并等待解析完成后，这里会显示章节结构。</div>
                    )}
                </div>
            );
        }

        const sections = parsedDoc.sections || [];
        const roots = buildSectionTree(sections);
        const allIndices = sections.map((_, idx) => idx);
        const selectedSet = new Set(selectedSectionIndices);
        const isOcr = !!parsedDoc.ocr_markdown;

        const selectMany = (indices: number[], checked: boolean) => {
            setSelectedSectionIndices((prev) => {
                const set = new Set(prev);
                for (const i of indices) {
                    if (checked) set.add(i);
                    else set.delete(i);
                }
                return Array.from(set).sort((a, b) => a - b);
            });
        };

        const activeSection = activePreviewIdx !== null ? sections[activePreviewIdx] : null;
        const selectedCharCount = selectedSectionIndices.reduce((acc, idx) => {
            const s = sections[idx];
            return acc + ((s?.content || s?.text || '') as string).length;
        }, 0);

        const renderNodes = (nodes: SectionNode[], depth: number): React.ReactElement[] => {
            return nodes.map((node) => {
                const key = `node-${node.idx}`;
                const isChecked = selectedSet.has(node.idx);
                const isActive = activePreviewIdx === node.idx;
                const indentPx = depth * 16;

                return (
                    <div key={key}>
                        <div
                            className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${isActive ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted/50'}`}
                            style={{ marginLeft: `${indentPx}px` }}
                        >
                            <input
                                type="checkbox"
                                className="shrink-0 accent-primary"
                                checked={isChecked}
                                onChange={(e) => { e.stopPropagation(); selectMany([node.idx], e.target.checked); }}
                                onClick={(e) => e.stopPropagation()}
                            />
                            <span
                                className={`text-sm flex-1 truncate ${depth === 0 ? 'font-medium' : 'text-muted-foreground'} ${isActive ? 'text-primary font-medium' : ''}`}
                                onClick={() => setActivePreviewIdx(isActive ? null : node.idx)}
                                title={node.title}
                            >
                                {node.title}
                            </span>
                            <Eye
                                className={`w-3.5 h-3.5 shrink-0 transition-opacity ${isActive ? 'opacity-100 text-primary' : 'opacity-0 group-hover:opacity-50'}`}
                                onClick={() => setActivePreviewIdx(isActive ? null : node.idx)}
                            />
                        </div>
                        {node.children.length > 0 && (
                            <div className="mt-0.5 space-y-0.5">
                                {renderNodes(node.children, depth + 1)}
                            </div>
                        )}
                    </div>
                );
            });
        };

        return (
            <div className="flex flex-col h-full gap-0">
                {/* Toolbar */}
                <div className="flex items-center justify-between gap-2 px-1 pb-2 border-b shrink-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <button
                            className="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors"
                            onClick={() => selectMany(allIndices, true)}
                        >全选</button>
                        <button
                            className="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors"
                            onClick={() => selectMany(allIndices, false)}
                        >全不选</button>
                        <button
                            className="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors"
                            onClick={() => { const n: Record<string, boolean> = {}; for (const r of roots) n[`sec-${r.idx}`] = false; setCollapsedGroups(n); }}
                        >展开全部</button>
                        <button
                            className="text-xs px-2 py-1 rounded border hover:bg-muted transition-colors"
                            onClick={() => { const n: Record<string, boolean> = {}; for (const r of roots) n[`sec-${r.idx}`] = true; setCollapsedGroups(n); }}
                        >折叠全部</button>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                        {isOcr && (
                            <button
                                className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-blue-300 text-blue-600 hover:bg-blue-50 transition-colors"
                                onClick={() => handleDownloadMarkdown(parsedDoc)}
                                title="下载 OCR Markdown"
                            >
                                <FileDown className="w-3.5 h-3.5" />
                                <span>下载 MD</span>
                            </button>
                        )}
                    </div>
                </div>

                {/* Status bar */}
                <div className="flex items-center gap-3 px-1 py-1.5 text-xs text-muted-foreground border-b shrink-0">
                    <span className="flex items-center gap-1">
                        {isOcr
                            ? <><ScanText className="w-3 h-3 text-blue-500" /><span className="text-blue-600 font-medium">PaddleOCR</span></>
                            : <><FileText className="w-3 h-3" /><span>结构解析</span></>
                        }
                    </span>
                    {parsedDoc.page_count && <span>{parsedDoc.page_count} 页</span>}
                    <span className="ml-auto font-medium text-foreground">{selectedSectionIndices.length}/{sections.length} 段已选</span>
                    {selectedCharCount > 0 && <span>≈ {(selectedCharCount / 500).toFixed(0)} 段落</span>}
                </div>

                {/* Main content: left tree + right preview */}
                <div className="flex-1 overflow-hidden flex min-h-0">
                    {/* Left: section tree */}
                    <div className="w-[55%] overflow-y-auto pr-1 border-r py-2 space-y-0.5">
                        {roots.map((chapter) => {
                            const indices = collectIndices(chapter);
                            const selectedCount = indices.reduce((acc, i) => acc + (selectedSet.has(i) ? 1 : 0), 0);
                            const allChecked = selectedCount === indices.length && indices.length > 0;
                            const partiallyChecked = selectedCount > 0 && selectedCount < indices.length;
                            const groupKey = `sec-${chapter.idx}`;
                            const isCollapsed = collapsedGroups[groupKey] ?? true;
                            const isActive = activePreviewIdx === chapter.idx;

                            return (
                                <div key={groupKey}>
                                    <div className={`flex items-center gap-2 px-2 py-2 rounded cursor-pointer transition-colors ${isActive ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted/50'}`}>
                                        <input
                                            type="checkbox"
                                            className="shrink-0 accent-primary"
                                            checked={allChecked}
                                            ref={(el) => { if (el) el.indeterminate = partiallyChecked; }}
                                            onChange={(e) => selectMany(indices, e.target.checked)}
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                        <span
                                            className={`text-sm font-semibold flex-1 min-w-0 truncate ${isActive ? 'text-primary' : ''}`}
                                            onClick={() => setActivePreviewIdx(isActive ? null : chapter.idx)}
                                            title={chapter.title}
                                        >
                                            {chapter.title}
                                        </span>
                                        <span className="text-xs text-muted-foreground shrink-0">{selectedCount}/{indices.length}</span>
                                        <button
                                            className="text-muted-foreground hover:text-foreground shrink-0"
                                            onClick={() => setCollapsedGroups(prev => ({ ...prev, [groupKey]: !isCollapsed }))}
                                        >
                                            {isCollapsed
                                                ? <ChevronRight className="w-3.5 h-3.5" />
                                                : <ChevronLeft className="w-3.5 h-3.5 rotate-90" />
                                            }
                                        </button>
                                    </div>
                                    {!isCollapsed && chapter.children.length > 0 && (
                                        <div className="mt-0.5 space-y-0.5">
                                            {renderNodes(chapter.children, 1)}
                                        </div>
                                    )}
                                    {!isCollapsed && chapter.children.length === 0 && (
                                        <div className="ml-7 py-1 text-xs text-muted-foreground">无子章节</div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Right: content preview */}
                    <div className="w-[45%] overflow-y-auto pl-3 py-2">
                        {activeSection ? (
                            <div>
                                <div className="flex items-start gap-2 mb-3">
                                    <div>
                                        <h4 className="text-sm font-semibold leading-tight">{(activeSection as any).title || `Section ${activePreviewIdx! + 1}`}</h4>
                                        {(activeSection as any).page_start != null && (
                                            <span className="text-xs text-muted-foreground">第 {(activeSection as any).page_start + 1} 页</span>
                                        )}
                                    </div>
                                </div>
                                <div className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap break-words">
                                    {((activeSection as any).content || (activeSection as any).text || '（无内容预览）').slice(0, 2000)}
                                    {((activeSection as any).content || (activeSection as any).text || '').length > 2000 && (
                                        <span className="text-muted-foreground italic">…（内容较长，已截断）</span>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-2 py-8">
                                <Eye className="w-8 h-8 opacity-30" />
                                <p className="text-xs">点击左侧章节标题<br/>在此预览内容</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="h-[calc(100vh-6rem)] flex gap-4 overflow-hidden">

            {/* Column 1: Parsed Structure (primary) */}
            {showStructure ? (
                <Card className="w-[520px] xl:w-[600px] 2xl:w-[680px] flex flex-col h-full border-r shadow-none shrink-0">
                    <CardHeader className="bg-muted/30 border-b py-4">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg flex items-center">
                                <FileText className="w-5 h-5 mr-2 text-primary" />
                                论文结构
                            </CardTitle>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowStructure(false)}
                                title="收起论文结构"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-hidden p-0 flex flex-col">
                        <div className="px-4 py-2 border-b bg-background shrink-0">
                            <div className="text-xs text-muted-foreground">
                                勾选章节以限定提示词生成范围，点击标题可预览内容。
                            </div>
                        </div>
                        <div className="flex-1 overflow-hidden p-4 flex flex-col">
                            {renderParsedStructure()}
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <div className="h-full w-10 shrink-0 flex items-center justify-center border rounded bg-card">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowStructure(true)}
                        title="展开论文结构"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </Button>
                </div>
            )}

            {/* Column 2: Documents + Settings (secondary) */}
            {showDocs ? (
                <Card className="w-[360px] xl:w-[400px] flex flex-col h-full border-r shadow-none shrink-0">
                    <CardHeader className="bg-muted/30 border-b py-4">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg flex items-center">
                                <FileText className="w-5 h-5 mr-2 text-primary" />
                                参考文档
                            </CardTitle>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowDocs(false)}
                                title="收起参考文档"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-hidden p-0 flex flex-col">

                    {/* Upload + settings (secondary) */}
                    <div className="bg-background">
                        <div className="p-4 border-b">
                            <div className="text-sm font-medium text-muted-foreground mb-2">你想生成什么图？（可选）</div>
                            <Textarea
                                value={promptRequest}
                                onChange={(e) => setPromptRequest(e.target.value)}
                                placeholder="例如：只生成一张整体架构图（包含输入、编码器、融合模块、输出），突出本文主要贡献点。"
                                className="min-h-[70px]"
                                disabled={templateMode}
                            />
                            <div className="flex items-center justify-between gap-2 mt-3">
                                <div className="text-sm font-medium text-muted-foreground">生成方式</div>
                                <Select value={promptMode} onValueChange={(v) => setPromptMode(v as any)}>
                                    <SelectTrigger className="w-[180px]">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="overall">整体架构图（1条）</SelectItem>
                                        <SelectItem value="sections">按章节生成（多条）</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <label className="flex items-center gap-2 mt-3 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={templateMode}
                                    onChange={(e) => setTemplateMode(e.target.checked)}
                                    className="w-4 h-4 accent-primary"
                                />
                                <span className="text-sm font-medium">只画底图（无文字）</span>
                            </label>
                            {templateMode && (
                                <p className="text-xs text-muted-foreground mt-1">
                                    生成纯结构底图，所有方块、箭头均无文字标注，方便自行填写内容。
                                </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-2">
                                章节勾选对两种方式都生效（用于限定参考范围）。
                            </p>
                        </div>

                        <div className="p-4 border-b">
                            <div
                                className="border-2 border-dashed rounded-lg p-4 text-center hover:bg-muted/50 transition-colors cursor-pointer"
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <input type="file" ref={fileInputRef} className="hidden" accept=".pdf,.docx,.txt" onChange={handleFileUpload} />
                                <FileUp className="w-7 h-7 mx-auto text-muted-foreground mb-2" />
                                <p className="text-sm font-medium">点击或拖拽以上传</p>
                                <p className="text-xs text-muted-foreground mt-1">支持 PDF, DOCX, TXT (最大 50MB)</p>
                            </div>

                            {isUploading && (
                                <div className="mt-4 space-y-2">
                                    <div className="flex justify-between text-xs">
                                        <span>上传中...</span>
                                        <span>{uploadProgress}%</span>
                                    </div>
                                    <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                                        <div className="bg-primary h-full transition-all" style={{ width: `${uploadProgress}%` }} />
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-b">
                            <div className="text-sm font-medium text-muted-foreground mb-2">已上传文档</div>
                            {documents.length === 0 ? (
                                <div className="text-sm text-muted-foreground">暂无文档，请先上传 PDF / DOCX / TXT。</div>
                            ) : (
                                <div className="space-y-2">
                                    {documents.map((doc) => (
                                        <div key={doc.id} className="p-3 bg-muted/20 rounded border space-y-2">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="min-w-0">
                                                    <p className="text-sm font-medium truncate">{doc.original_filename}</p>
                                                    {doc.parse_status === 'failed' && doc.parse_error && (
                                                        <p className="text-xs text-destructive mt-1 line-clamp-2">{doc.parse_error}</p>
                                                    )}
                                                    {doc.parse_status === 'completed' && doc.ocr_markdown && (
                                                        <p className="text-xs text-blue-600 mt-0.5 flex items-center gap-1">
                                                            <ScanText className="w-3 h-3" /> PaddleOCR 解析
                                                        </p>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-1.5 shrink-0">
                                                    {(doc.parse_status === 'parsing' || doc.parse_status === 'pending') && (
                                                        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                                                    )}
                                                    {doc.parse_status === 'completed' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                                                    {doc.parse_status === 'failed' && <AlertCircle className="w-4 h-4 text-destructive" />}
                                                    <Badge variant={doc.parse_status === 'completed' ? 'secondary' : doc.parse_status === 'failed' ? 'destructive' : 'outline'} className="text-xs">
                                                        {doc.parse_status === 'completed' ? '已解析' : doc.parse_status === 'failed' ? '失败' : doc.parse_status === 'parsing' ? '解析中' : '待解析'}
                                                    </Badge>
                                                </div>
                                            </div>
                                            {/* OCR button for PDFs */}
                                            {doc.file_type === 'pdf' && (
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded border transition-colors border-blue-300 text-blue-600 hover:bg-blue-50 cursor-pointer"
                                                        disabled={ocrLoading[doc.id] || doc.parse_status === 'parsing'}
                                                        onClick={() => handleTriggerOcr(doc)}
                                                        title="OCR 解析此 PDF"
                                                    >
                                                        {ocrLoading[doc.id]
                                                            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                            : <ScanText className="w-3.5 h-3.5" />
                                                        }
                                                        {ocrLoading[doc.id] ? 'OCR 解析中…' : 'OCR 重新解析'}
                                                    </button>
                                                    {doc.ocr_markdown && (
                                                        <button
                                                            className="flex items-center gap-1 text-xs px-2 py-1.5 rounded border border-muted text-muted-foreground hover:bg-muted transition-colors"
                                                            onClick={() => handleDownloadMarkdown(doc)}
                                                        >
                                                            <FileDown className="w-3.5 h-3.5" /> 下载 MD
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                    </CardContent>
                    <CardFooter className="p-4 border-t bg-muted/10">
                        <Button className="w-full font-semibold" onClick={handleAutoGenerate} disabled={isAutoGenerating}>
                            {isAutoGenerating ? (
                                <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> 生成配图中...</>
                            ) : (
                                <><Send className="w-4 h-4 mr-2" /> 生成配图</>
                            )}
                        </Button>
                    </CardFooter>
                </Card>
            ) : (
                <div className="h-full w-10 shrink-0 flex items-center justify-center border rounded bg-card">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowDocs(true)}
                        title="展开参考文档"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </Button>
                </div>
            )}

            {/* Right Column: Image Cards (no tabs) */}
            <div className="flex-1 flex flex-col h-full">
                <div className="bg-muted/30 border-b py-4 px-6 flex items-center">
                    <ImageIcon className="w-5 h-5 mr-2 text-primary" />
                    <h3 className="text-lg font-semibold">配图生成</h3>
                    {isRefreshing && <RefreshCw className="w-4 h-4 ml-3 animate-spin text-muted-foreground" />}
                </div>
                <ScrollArea className="flex-1">
                    <div className="p-4">
                        {prompts.length === 0 ? (
                            <div className="text-center text-muted-foreground mt-20">
                                {isAutoGenerating ? (
                                    <div className="flex flex-col items-center gap-2">
                                        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                                        <span>正在生成配图...</span>
                                    </div>
                                ) : (
                                    '上传文档后点击"生成配图"开始。'
                                )}
                            </div>
                        ) : (
                            <div className="space-y-6">
                                {prompts.map(prompt => {
                                    const promptImgs = images.filter(img => img.prompt_id === prompt.id);
                                    const latestImg = promptImgs.length > 0
                                        ? promptImgs.reduce((a: any, b: any) =>
                                            new Date(b.created_at || 0).getTime() > new Date(a.created_at || 0).getTime() ? b : a
                                        )
                                        : null;
                                    const settings = getSettings(prompt.id);
                                    const isCompleted = latestImg?.generation_status === 'completed';
                                    const isProcessing = latestImg
                                        ? IMAGE_IN_PROGRESS_STATUSES.has(latestImg.generation_status)
                                        : false;

                                    return (
                                        <Card key={prompt.id} className="overflow-hidden">
                                            {/* Image Preview */}
                                            <div className="aspect-video bg-muted relative">
                                                {isCompleted && latestImg && imagePreviews[latestImg.id] ? (
                                                    <img
                                                        src={imagePreviews[latestImg.id]}
                                                        alt={prompt.title || 'Generated Figure'}
                                                        className="w-full h-full object-cover"
                                                        onError={() => {
                                                            setImagePreviews(prev => {
                                                                const next = { ...prev };
                                                                delete next[latestImg.id];
                                                                return next;
                                                            });
                                                        }}
                                                    />
                                                ) : isCompleted && latestImg ? (
                                                    <div className="absolute inset-0 flex items-center justify-center flex-col gap-2">
                                                        <ImageIcon className="h-8 w-8 text-muted-foreground" />
                                                        <Button
                                                            size="sm"
                                                            variant="secondary"
                                                            disabled={!!isPreviewing[latestImg.id]}
                                                            onClick={() => ensureImagePreview(latestImg.id)}
                                                        >
                                                            {isPreviewing[latestImg.id] ? '加载中...' : '预览'}
                                                        </Button>
                                                    </div>
                                                ) : isProcessing ? (
                                                    <div className="absolute inset-0 flex items-center justify-center flex-col">
                                                        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                                                        <span className="mt-2 text-sm font-medium">生成中...</span>
                                                    </div>
                                                ) : (
                                                    <div className="absolute inset-0 flex items-center justify-center flex-col">
                                                        <ImageIcon className="h-8 w-8 text-muted-foreground" />
                                                        <span className="mt-2 text-sm text-muted-foreground">
                                                            {latestImg ? latestImg.generation_status : '待生成'}
                                                        </span>
                                                    </div>
                                                )}
                                            </div>

                                            {/* Title + Type Badge */}
                                            <CardHeader className="pb-2">
                                                <div className="flex justify-between items-center">
                                                    <CardTitle className="text-base">
                                                        {prompt.title || `Figure ${prompt.figure_number ?? ''}`}
                                                    </CardTitle>
                                                    <Badge>{prompt.suggested_figure_type || '未分类'}</Badge>
                                                </div>
                                            </CardHeader>

                                            {/* Per-card Settings */}
                                            <CardContent className="pb-3">
                                                <div className="grid grid-cols-3 gap-2">
                                                    <div>
                                                        <label className="text-xs text-muted-foreground mb-1 block">配色</label>
                                                        <Select
                                                            value={settings.colorScheme}
                                                            onValueChange={(v) => updateSetting(prompt.id, 'colorScheme', v)}
                                                        >
                                                            <SelectTrigger className="h-8 text-xs">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {colorSchemes.length > 0 ? (
                                                                    colorSchemes.map(scheme => {
                                                                        const val = typeof scheme === 'string' ? scheme : (scheme.name || scheme.id);
                                                                        const label = typeof scheme === 'string' ? scheme : (scheme.display_name || scheme.name || scheme.id);
                                                                        return <SelectItem key={val} value={val}>{label}</SelectItem>;
                                                                    })
                                                                ) : (
                                                                    <SelectItem value="okabe-ito">Okabe-Ito</SelectItem>
                                                                )}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-muted-foreground mb-1 block">比例</label>
                                                        <Select
                                                            value={settings.aspectRatio}
                                                            onValueChange={(v) => updateSetting(prompt.id, 'aspectRatio', v)}
                                                        >
                                                            <SelectTrigger className="h-8 text-xs">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {['1:1', '4:3', '3:4', '16:9', '9:16', '3:2', '2:3'].map(r => (
                                                                    <SelectItem key={r} value={r}>{r}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-muted-foreground mb-1 block">分辨率</label>
                                                        <Select
                                                            value={settings.resolution}
                                                            onValueChange={(v) => updateSetting(prompt.id, 'resolution', v)}
                                                        >
                                                            <SelectTrigger className="h-8 text-xs">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {['1K', '2K', '4K'].map(r => (
                                                                    <SelectItem key={r} value={r}>{r}</SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>

                                                    </div>
                                                </div>
                                            </CardContent>

                                            {/* Action Buttons */}
                                            <CardFooter className="flex gap-2 border-t pt-3">
                                                {!latestImg ? (
                                                    <Button size="sm" onClick={() => handleGenerateImage(prompt.id)}>
                                                        <ImageIcon className="mr-2 h-4 w-4" />
                                                        生成图片
                                                    </Button>
                                                ) : (
                                                    <>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleGenerateImage(prompt.id)}
                                                            disabled={isProcessing}
                                                        >
                                                            <RefreshCw className="mr-1 h-3 w-3" />
                                                            重新生成
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            disabled={!isCompleted || isDownloading === latestImg.id}
                                                            onClick={() => handleDownloadImage(latestImg.id)}
                                                        >
                                                            <Download className="mr-1 h-3 w-3" />
                                                            下载
                                                        </Button>
                                                    </>
                                                )}
                                            </CardFooter>

                                            {/* Edit (image-to-image) section */}
                                            {isCompleted && latestImg && (
                                                <div className="border-t px-4 py-3">
                                                    <div className="flex gap-2">
                                                        <input
                                                            type="text"
                                                            className="flex-1 h-8 rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                            placeholder="输入改图需求..."
                                                            value={editInstructions[latestImg.id] || ''}
                                                            onChange={(e) => setEditInstructions(prev => ({ ...prev, [latestImg.id]: e.target.value }))}
                                                            onKeyDown={(e) => {
                                                                if (e.key === 'Enter' && !e.shiftKey) {
                                                                    e.preventDefault();
                                                                    handleEditImage(latestImg.id);
                                                                }
                                                            }}
                                                        />
                                                        <Button
                                                            size="sm"
                                                            disabled={!editInstructions[latestImg.id]?.trim() || !!isEditing[latestImg.id]}
                                                            onClick={() => handleEditImage(latestImg.id)}
                                                        >
                                                            {isEditing[latestImg.id] ? (
                                                                <RefreshCw className="h-4 w-4 animate-spin" />
                                                            ) : (
                                                                <Send className="h-4 w-4" />
                                                            )}
                                                        </Button>
                                                    </div>
                                                </div>
                                            )}
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </div>
        </div>
    );
}
