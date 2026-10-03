import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = process.env.PLAYWRIGHT_MODULE
  ? await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href)
  : await import('playwright');
const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5175';
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) });
const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const imageBase64 = await page.evaluate(() => {
  const canvas = document.createElement('canvas'); canvas.width = 1200; canvas.height = 360;
  const c = canvas.getContext('2d'); c.fillStyle = '#fff'; c.fillRect(0, 0, 1200, 360);
  for (const [i, color] of ['#dbeafe', '#d1fae5', '#ffe4e6'].entries()) {
    c.fillStyle = color; c.fillRect(35 + i * 400, 70, 300, 210);
    c.fillStyle = '#172027'; c.font = '28px sans-serif'; c.fillText(['Input data', 'Feature encoder', 'Prediction'][i], 65 + i * 400, 180);
    if (i < 2) { c.fillRect(335 + i * 400, 165, 100, 4); }
  }
  return canvas.toDataURL('image/png').split(',')[1];
});
const stamp = '2026-10-04T05:00:00Z';
const spec = { version: 1, title: 'Source-linked framework', caption: 'Test evidence', direction: 'LR', nodes: [{ id: 'input', label: 'Data', role: 'input', sources: [{ section_index: 0, quote: 'Input data' }] }, { id: 'output', label: 'Prediction', role: 'output', sources: [] }], edges: [{ id: 'flow', source: 'input', target: 'output', label: '', kind: 'data', sources: [] }], groups: [] };
const project = { id: 'project-1', name: 'Multimodal research figures', description: 'Architecture and evidence', color_scheme: 'okabe-ito', style_preset: 'classic', paper_field: 'Machine learning', document_count: 2, prompt_count: 2, image_count: 3, status: 'active', created_at: stamp };
const documents = [
  { id: 'doc-1', project_id: project.id, original_filename: 'paper-one.pdf', file_type: 'pdf', file_size_bytes: 12000, page_count: 12, parse_status: 'completed', sections: [{ index: 0, title: '1. Introduction', content: 'Input data', level: 1 }], created_at: stamp },
  { id: 'doc-2', project_id: project.id, original_filename: 'paper-two.docx', file_type: 'docx', file_size_bytes: 16000, page_count: null, parse_status: 'completed', sections: [{ index: 7, title: '7. Experiments', content: 'Experimental evidence', level: 1 }, { index: 11, title: '8. Results', content: '| A | B |\n| 1 | 2 |', level: 1 }], created_at: stamp },
];
let prompt = { id: 'prompt-1', project_id: project.id, document_id: 'doc-1', figure_number: 1, title: 'Source-linked framework', original_prompt: 'Original prompt', edited_prompt: null, active_prompt: 'Original prompt', suggested_figure_type: 'overall_framework', suggested_aspect_ratio: '16:9', source_sections: [0], generation_status: 'completed', generation_model: 'fixture-text-model', revision: 1, figure_spec: spec, style_preset: 'classic', created_at: stamp };
let revisions = [{ id: 'revision-1', revision: 1, prompt_text: 'Original prompt', figure_spec: spec, created_at: stamp }];
const baseImage = { project_id: project.id, prompt_id: prompt.id, resolution: '2K', aspect_ratio: '16:9', color_scheme: project.color_scheme, width_px: 1200, height_px: 360, generation_duration_ms: 13500, generation_status: 'completed', generation_model: 'fixture-image-model', quality: 'max', prompt_revision: 1, style_preset: 'classic', favorite: false, selected: false, created_at: stamp };
let images = [{ ...baseImage, id: 'image-2', parent_image_id: 'image-1' }, { ...baseImage, id: 'image-1' }, { ...baseImage, id: 'image-3', generation_status: 'interrupted', generation_error: 'Interrupted by restart' }];
const makeJob = (id, kind, status) => ({ id, kind, status, project_id: project.id, stage: 'fixture', resource_id: null, result: null, error: null, retry_of: null, created_at: stamp, started_at: status === 'running' ? stamp : null, finished_at: null });
let jobs = [makeJob('job-running', 'image', 'running'), makeJob('job-failed', 'image', 'failed'), makeJob('job-queued', 'prompt', 'queued')];
const exports = [];
const colors = { primary: '#006699', secondary: '#E69F00', tertiary: '#009E73', text: '#333333', fill: '#FFFFFF', section_bg: '#F7F7F7', border: '#CCCCCC', arrow: '#4D4D4D' };
const palettes = [{ id: 'seeded-preset-uuid', slug: 'okabe-ito', name: 'Okabe-Ito', type: 'preset', colors }, { id: 'custom-palette', slug: null, name: 'Research palette', type: 'custom', colors }];
const config = { api_key_configured: true, api_key_source: 'environment', api_base: 'https://api.example.invalid/v1', text_model: 'fixture-text-model', text_reasoning_effort: 'max', text_max_output_tokens: 8000, image_model: 'fixture-image-model', image_quality: 'max', max_upload_size_mb: 30, max_concurrent_jobs: 2, styles: [{ id: 'classic', name: 'Classic', description: 'Classic' }, { id: 'pastel', name: 'Pastel', description: 'Pastel' }], profiles: [{ id: 'quality', name: 'Quality', text_reasoning_effort: 'max', image_quality: 'max' }], usage_summary: { jobs_completed: 10, jobs_failed: 1, input_tokens: null, output_tokens: 250, image_count: 2, duration_ms: 1000 } };
let conflict = true;
let failNextDirect = false;
const mutations = [];
let receivedMask;

// Fail closed: every API request is mocked; no request reaches a real backend.
await context.route('**/api/**', async route => {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname.replace('/api/v1', '');
  const method = request.method();
  let body;
  if (request.headers()['content-type']?.includes('application/json')) body = request.postDataJSON();
  if (method !== 'GET') mutations.push({ path, method, body });
  const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
  if (path === '/configuration') return json(config);
  if (path === '/configuration/check') return json({ ok: true, model_access: true });
  if (path === '/color-schemes/') return json(palettes);
  if (path === '/projects/') return json({ items: [project], total: 1 });
  if (path === `/projects/${project.id}`) { if (method === 'PUT') Object.assign(project, body); return json(project); }
  if (path.endsWith('/documents')) return json(documents);
  if (path.endsWith('/prompts')) return json([prompt, { ...prompt, id: 'prompt-2', title: 'Legacy prompt', figure_number: 2, figure_spec: null }]);
  if (path.endsWith('/prompt-jobs')) { const job = makeJob('job-prompt', 'prompt', 'queued'); jobs = [job, ...jobs]; return json(job, 202); }
  if (path === `/prompts/${prompt.id}` && method === 'PUT') {
    if (conflict) { conflict = false; prompt = { ...prompt, revision: 2, active_prompt: 'Server revision' }; return json({ detail: 'Stale revision' }, 409); }
    assert.equal(body.expected_revision, prompt.revision);
    prompt = { ...prompt, revision: prompt.revision + 1, active_prompt: body.edited_prompt, edited_prompt: body.edited_prompt, figure_spec: Object.hasOwn(body, 'figure_spec') ? body.figure_spec : (body.edited_prompt === prompt.active_prompt ? prompt.figure_spec : null) };
    revisions = [...revisions, { id: `revision-${prompt.revision}`, revision: prompt.revision, prompt_text: prompt.active_prompt, figure_spec: prompt.figure_spec, created_at: stamp }];
    return json(prompt);
  }
  if (path.endsWith('/revisions')) return json(revisions);
  if (path.endsWith('/restore')) { assert.equal(body.expected_revision, prompt.revision); const old = revisions.find(r => r.revision === body.revision); prompt = { ...prompt, revision: prompt.revision + 1, active_prompt: old.prompt_text, figure_spec: old.figure_spec }; return json(prompt); }
  if (path.endsWith('/spec-jobs')) { const job = { ...makeJob('job-spec', 'spec', 'succeeded'), result: { applied: false, figure_spec: spec, message: 'Prompt changed during derivation; retained spec was not applied.' } }; jobs = [job, ...jobs]; return json(job, 202); }
  if (path.endsWith('/images/generate') || path === '/images/generate-direct') {
    if (path === '/images/generate-direct' && failNextDirect) { failNextDirect = false; return route.abort('failed'); }
    const image = { ...baseImage, id: `image-${images.length + 1}`, generation_status: 'pending', job_id: `job-image-${images.length + 1}` };
    images = [image, ...images]; jobs = [makeJob(image.job_id, 'image', 'queued'), ...jobs];
    return json({ id: image.id, generation_status: image.generation_status, job_id: image.job_id }, 202);
  }
  if (path.endsWith('/images')) return json(images);
  if (path === '/jobs') return json(jobs);
  if (path.endsWith('/cancel')) { const id = path.split('/')[2]; jobs = jobs.map(j => j.id === id ? { ...j, status: 'cancelled' } : j); return json(jobs.find(j => j.id === id)); }
  if (path.endsWith('/retry')) { const job = { ...makeJob('job-retried', 'image', 'queued'), retry_of: 'job-failed' }; jobs = [job, ...jobs]; return json(job); }
  if (path.endsWith('/exports') && method === 'POST') { exports.push({ id: 'export-1', prompt_id: prompt.id, format: body.format, created_at: stamp, generation_status: 'completed', width_px: body.width, height_px: 600, job_id: 'job-export' }); return json(makeJob('job-export', 'export', 'succeeded'), 202); }
  if (path.endsWith('/exports')) return json(exports);
  if (path === '/exports/export-1/download') return route.fulfill({ contentType: 'application/xml', body: '<mxfile/>' });
  if (path.endsWith('/download')) return route.fulfill({ contentType: 'image/png', body: Buffer.from(imageBase64, 'base64') });
  if (path.endsWith('/provenance')) return json({ prompt: 'Saved inputs', api_key: 'fixture-credential-should-not-render', generation_metadata: { api_key_prefix: 'hidden-prefix', style_preset: 'classic', input_tokens: null } });
  if (path.endsWith('/edit')) {
    const form = await new Response(request.postDataBuffer(), { headers: { 'content-type': request.headers()['content-type'] } }).formData();
    const file = form.get('mask_image');
    receivedMask = { base64: Buffer.from(await file.arrayBuffer()).toString('base64'), instruction: form.get('edit_instruction'), reference: form.get('reference_image')?.name, idempotency: form.get('idempotency_key') };
    const image = { ...baseImage, id: 'image-edited', parent_image_id: path.split('/')[2], generation_status: 'pending', job_id: 'job-edited' }; images = [image, ...images];
    return json(image, 202);
  }
  if (path.startsWith('/images/')) { const image = images.find(i => i.id === path.split('/')[2]); if (method === 'PATCH') Object.assign(image, body); return json(image); }
  return json({ detail: `Unmocked ${method} ${path}` }, 404);
});
await mkdir('output/playwright', { recursive: true });
try {
  await page.goto(`${base}/projects/${project.id}`);
  await page.getByRole('heading', { name: project.name }).waitFor();
  const documentsPanel = page.getByRole('region', { name: 'Documents', exact: true });
  assert.equal(await documentsPanel.getByLabel('Source document', { exact: true }).inputValue(), '');
  await documentsPanel.getByLabel('Source document', { exact: true }).selectOption('doc-2');
  const paletteSelect = documentsPanel.getByLabel('Palette', { exact: true });
  assert.equal(await paletteSelect.inputValue(), 'seeded-preset-uuid');
  assert.deepEqual(await paletteSelect.locator('option').allTextContents(), ['Okabe-Ito', 'Research palette']);
  assert.equal(await documentsPanel.locator('[aria-label="Palette colors"] > span').count(), 8);
  assert.equal(await documentsPanel.locator('[aria-label="Palette colors"] > span').first().getAttribute('title'), `primary: ${colors.primary}`);
  await documentsPanel.getByLabel('Scope', { exact: true }).selectOption('sections');
  await documentsPanel.getByLabel('7. Experiments', { exact: true }).check();
  await documentsPanel.getByLabel('Style', { exact: true }).selectOption('pastel');
  await documentsPanel.getByLabel('Figure request', { exact: true }).fill('Experimental workflow');
  await documentsPanel.getByRole('button', { name: 'Generate prompts', exact: true }).click();
  await page.waitForFunction(() => document.body.textContent.includes('Jobs (4)'));
  const promptRequest = mutations.find(m => m.path.endsWith('/prompt-jobs')).body;
  assert.equal(promptRequest.document_id, 'doc-2'); assert.deepEqual(promptRequest.section_indices, [7]);
  assert.equal(promptRequest.style_preset, 'pastel'); assert.equal(promptRequest.custom_colors.primary, colors.primary);
  assert.equal(promptRequest.color_scheme, 'seeded-preset-uuid');
  assert.ok(promptRequest.idempotency_key);
  await documentsPanel.getByLabel('Source document', { exact: true }).selectOption('doc-1');
  assert.equal(await documentsPanel.getByLabel('Scope', { exact: true }).inputValue(), 'all');

  const editor = page.getByRole('article', { name: 'Source-linked framework', exact: true });
  await editor.getByLabel('Prompt text', { exact: true }).fill('Preserved local draft');
  await editor.getByRole('button', { name: 'Save revision', exact: true }).click();
  await editor.getByText('This prompt changed on the server. Your draft is preserved.').waitFor();
  assert.equal(await editor.getByLabel('Prompt text', { exact: true }).inputValue(), 'Preserved local draft');
  await editor.getByRole('button', { name: 'Keep draft on latest revision', exact: true }).click();
  await editor.getByRole('button', { name: 'Save revision', exact: true }).click();
  await page.waitForFunction(() => document.body.textContent.includes('Revision 3'));
  const saves = mutations.filter(m => m.method === 'PUT' && m.path === `/prompts/${prompt.id}`);
  assert.deepEqual(saves.map(m => m.body.expected_revision), [1, 2]);
  assert.equal(saves[1].body.figure_spec, undefined, 'Text-only saves must allow backend spec invalidation');
  assert.equal(prompt.figure_spec, null);

  await editor.getByRole('button', { name: 'Revision history', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Restore', exact: true }).first().waitFor();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('dialog').getByRole('button', { name: 'Restore', exact: true }).first().click();
  await page.waitForFunction(() => document.body.textContent.includes('Revision 4'));
  assert.equal(await editor.getByLabel('Prompt text', { exact: true }).inputValue(), 'Original prompt');
  await editor.getByRole('tab', { name: 'FigureSpec', exact: true }).click();
  await editor.getByLabel('FigureSpec JSON', { exact: true }).fill('{"version": 2}');
  assert.ok(await editor.getByRole('button', { name: 'Save revision', exact: true }).isDisabled());
  await editor.getByLabel('FigureSpec JSON', { exact: true }).fill(JSON.stringify(spec, null, 2));
  await editor.getByLabel('Format', { exact: true }).selectOption('drawio');
  await editor.getByLabel('Width (px)', { exact: true }).fill('1800');
  await editor.getByRole('button', { name: 'Export figure', exact: true }).click();
  await page.getByRole('tab', { name: 'Exports (1)', exact: true }).waitFor();
  assert.equal(mutations.find(m => m.path.endsWith('/exports')).body.width, 1800);
  await editor.getByRole('button', { name: 'Clear FigureSpec', exact: true }).click();
  assert.ok(await editor.getByLabel('FigureSpec JSON', { exact: true }).isVisible());
  assert.equal(await editor.getByLabel('FigureSpec JSON', { exact: true }).inputValue(), '');
  assert.ok(await editor.getByRole('button', { name: 'Save revision', exact: true }).isEnabled());
  assert.ok(await editor.getByRole('button', { name: 'Export figure', exact: true }).isDisabled());
  await editor.getByRole('button', { name: 'Save revision', exact: true }).click();
  await page.waitForFunction(() => document.body.textContent.includes('Revision 5'));
  assert.equal(mutations.filter(m => m.method === 'PUT' && m.path === `/prompts/${prompt.id}`).at(-1).body.figure_spec, null);
  assert.equal(prompt.figure_spec, null);
  assert.ok(await editor.getByLabel('FigureSpec JSON', { exact: true }).isVisible());
  assert.ok(await editor.getByRole('button', { name: 'Save revision', exact: true }).isDisabled());
  await editor.getByRole('tab', { name: 'Prompt', exact: true }).click();
  await editor.getByLabel('Prompt text', { exact: true }).fill('Text edited after clearing spec');
  await editor.getByRole('button', { name: 'Save revision', exact: true }).click();
  await page.waitForFunction(() => document.body.textContent.includes('Revision 6'));
  assert.equal(Object.hasOwn(mutations.filter(m => m.method === 'PUT' && m.path === `/prompts/${prompt.id}`).at(-1).body, 'figure_spec'), false);
  await page.getByRole('tab', { name: 'Exports (1)', exact: true }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download export', exact: true }).click();
  assert.ok((await download).suggestedFilename().endsWith('.drawio'));

  await page.getByRole('tab', { name: 'Jobs (4)', exact: true }).click();
  assert.ok(await page.getByText('Running image requests cannot be cancelled.').isVisible());
  await page.getByRole('button', { name: 'Cancel queued job', exact: true }).first().click();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Retry as a new attempt', exact: true }).click();
  await page.getByRole('tab', { name: 'Jobs (5)', exact: true }).waitFor();
  assert.equal(mutations.filter(m => m.path.endsWith('/retry')).length, 1);

  await page.getByRole('tab', { name: 'Prompts (2)', exact: true }).click();
  await page.getByLabel('Figure', { exact: true }).selectOption('prompt-2');
  const legacy = page.getByRole('article', { name: 'Legacy prompt', exact: true });
  await legacy.getByRole('tab', { name: 'FigureSpec', exact: true }).click();
  await legacy.getByRole('button', { name: 'Derive FigureSpec', exact: true }).click();
  await page.getByRole('tab', { name: 'Jobs (6)', exact: true }).click();
  await page.getByText('Prompt changed during derivation; retained spec was not applied.', { exact: true }).waitFor();
  const retainedDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download retained FigureSpec', exact: true }).click();
  assert.equal((await retainedDownload).suggestedFilename(), 'figure-spec-job-spec.json');

  await page.getByRole('tab', { name: 'Images (3)', exact: true }).click();
  await page.getByRole('button', { name: 'Favorite', exact: true }).first().click();
  await page.getByRole('button', { name: 'Remove favorite', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Select image', exact: true }).first().click();
  await page.getByRole('button', { name: 'Deselect image', exact: true }).waitFor();
  await page.getByLabel('Compare image 1', { exact: true }).check();
  await page.getByLabel('Compare image 2', { exact: true }).check();
  await page.getByRole('button', { name: 'Compare (2/2)', exact: true }).click();
  await page.getByRole('dialog').getByRole('heading', { name: 'Image comparison' }).waitFor();
  await page.screenshot({ path: 'output/playwright/comparison-desktop.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect image 1', exact: true }).click();
  await page.getByRole('dialog').getByRole('tab', { name: 'Edit', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Edit instruction', { exact: true }).fill('Highlight the middle encoder');
  await page.getByRole('dialog').locator('input[type=file]').setInputFiles({ name: 'reference.png', mimeType: 'image/png', buffer: Buffer.from(imageBase64, 'base64') });
  await page.getByRole('dialog').getByLabel('Edit mask', { exact: true }).check();
  const canvas = page.getByRole('img', { name: 'Mask drawing canvas' });
  await canvas.waitFor();
  const bounds = await canvas.boundingBox();
  await page.mouse.move(bounds.x + bounds.width * .45, bounds.y + bounds.height * .5);
  await page.mouse.down(); await page.mouse.move(bounds.x + bounds.width * .55, bounds.y + bounds.height * .5, { steps: 8 }); await page.mouse.up();
  await page.screenshot({ path: 'output/playwright/mask-desktop.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'Create edited version', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('textarea') !== null);
  for (let i = 0; i < 100 && !receivedMask; i++) await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(receivedMask.reference, 'reference.png'); assert.ok(receivedMask.idempotency);
  const maskPixels = await page.evaluate(async base64 => {
    const image = new Image(); image.src = `data:image/png;base64,${base64}`; await image.decode();
    const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
    const c = canvas.getContext('2d'); c.drawImage(image, 0, 0);
    return { width: image.width, height: image.height, center: c.getImageData(600, 180, 1, 1).data[3], corner: c.getImageData(5, 5, 1, 1).data[3] };
  }, receivedMask.base64);
  assert.deepEqual(maskPixels, { width: 1200, height: 360, center: 0, corner: 255 });
  await page.getByRole('dialog').getByRole('tab', { name: 'Provenance', exact: true }).click();
  await page.getByText('Saved inputs', { exact: false }).waitFor();
  assert.ok(!(await page.getByRole('dialog').innerText()).includes('fixture-credential'));
  assert.ok(!(await page.getByRole('dialog').innerText()).includes('hidden-prefix'));
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();

  await page.getByRole('link', { name: 'Direct generation', exact: true }).click();
  await page.getByLabel('Project', { exact: true }).selectOption(project.id);
  await page.getByLabel('Prompt', { exact: true }).fill('Direct image test');
  await page.getByLabel('Style', { exact: true }).selectOption('pastel');
  await page.getByLabel('Profile', { exact: true }).selectOption('draft');
  await page.getByLabel('Resolution', { exact: true }).selectOption('4K');
  await page.getByLabel('Aspect ratio', { exact: true }).selectOption('4:3');
  await page.getByRole('button', { name: 'Generate image', exact: true }).click();
  await page.getByRole('button', { name: 'Generate image', exact: true }).waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('button[type=submit]').disabled);
  const direct = mutations.find(m => m.path === '/images/generate-direct').body;
  assert.equal(direct.style_preset, 'pastel'); assert.equal(direct.profile, 'draft'); assert.equal(direct.resolution, '4K'); assert.equal(direct.aspect_ratio, '4:3'); assert.equal(direct.custom_colors.primary, colors.primary);
  failNextDirect = true;
  await page.getByRole('button', { name: 'Generate image', exact: true }).click();
  await page.getByText('The outcome is unknown.', { exact: false }).waitFor();
  const mutationCount = mutations.length;
  await page.waitForTimeout(5500);
  assert.equal(mutations.length, mutationCount, 'Polling must never retry a billed request');

  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('heading', { name: 'Effective settings', exact: true }).waitFor();
  await page.getByText('fixture-text-model', { exact: true }).waitFor();
  assert.equal(mutations.filter(m => m.path === '/configuration/check').length, 0);
  await page.getByRole('button', { name: 'Check connectivity & model access', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'model_access' }).waitFor();
  assert.equal(mutations.filter(m => m.path === '/configuration/check').length, 1);
  await page.getByRole('button', { name: '中文', exact: true }).click();
  await page.getByRole('heading', { name: '有效配置', exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/settings-zh-desktop.png', fullPage: true, animations: 'disabled' });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/projects/${project.id}`);
  await page.getByRole('heading', { name: project.name }).waitFor();
  assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile workspace must not overflow');
  await page.screenshot({ path: 'output/playwright/workspace-zh-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('tab', { name: /^图像/ }).click();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: 'output/playwright/images-zh-mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'EN', exact: true }).click();
  await page.getByRole('tab', { name: /^Prompts/ }).click();
  await page.screenshot({ path: 'output/playwright/workspace-en-mobile.png', fullPage: true, animations: 'disabled' });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  console.log('PASS: mocked browser workflow, conflicts/restores, explicit document and section IDs, palette/style parity, queued cancellation, explicit retry, exports/download, favorites/selection, comparison, reference/mask PNG pixels, provenance redaction, unknown-outcome no-retry, EN/ZH, desktop/mobile.');
} catch (error) {
  await page.screenshot({ path: 'output/playwright/failure.png', fullPage: true });
  console.error((await page.locator('body').innerText()).slice(0, 9000));
  throw error;
} finally {
  await browser.close();
}
