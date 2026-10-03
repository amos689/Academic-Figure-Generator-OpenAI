import assert from 'node:assert/strict';
import test from 'node:test';
import { AxiosError } from 'axios';
import api, { workbenchApi } from '../src/lib/api.ts';
import { parseFigureSpec } from '../src/lib/figureSpec.ts';
import { getApiErrorMessage, isRevisionConflict, isUnknownOutcome } from '../src/lib/apiError.ts';
import { maskPoint, paintStrokes } from '../src/lib/mask.ts';
import { figureSpecChanged, figureSpecPatch, readPromptDraft, storePromptDraft } from '../src/lib/promptDraft.ts';
import { DEFAULT_SETTINGS, activeStatus, completedStatus, canRetryJob, findPalette, imageAncestors, nonSecret, promptText, sectionIndex, settingsForPrompt, withPalette } from '../src/lib/workbench.ts';

const spec = {
  version: 1, title: 'Framework', caption: 'Evidence-linked flow', direction: 'LR',
  nodes: [{ id: 'in', label: 'Input', role: 'input', sources: [{ section_index: 7, quote: 'Input data' }] }, { id: 'out', label: 'Output', role: 'output', group_id: 'stage', sources: [] }],
  edges: [{ id: 'flow', source: 'in', target: 'out', label: '', kind: 'data', sources: [] }],
  groups: [{ id: 'stage', label: 'Stage' }],
};
const validate = (value, sections) => parseFigureSpec(JSON.stringify(value), sections);

test('FigureSpec validates version, identities, edges, groups, and section identifiers', () => {
  assert.deepEqual(validate(spec, [{ index: 7 }]).errors, []);
  assert.ok(validate(spec, [{ index: 0 }]).errors[0].includes('unknown section 7'));
  assert.ok(validate({ ...spec, version: 2 }).errors.length);
  assert.ok(validate({ ...spec, edges: [{ ...spec.edges[0], target: 'missing' }] }).errors.some(e => e.includes('Unknown node')));
  assert.ok(validate({ ...spec, groups: [{ id: 'in', label: 'Duplicate' }] }).errors.some(e => e.includes('Duplicate ID')));
  assert.ok(validate({ ...spec, groups: [] }).errors.some(e => e.includes('Unknown group')));
  assert.ok(validate({ ...spec, svg: '<script />' }).errors.length);
  assert.ok(validate({ ...spec, title: '<script>alert(1)</script>' }).errors.length);
  assert.ok(validate({ ...spec, title: '&lt;svg&gt;' }).errors.length);
  assert.ok(validate({ ...spec, title: 'a'.repeat(241) }).errors.length);
  assert.ok(validate(spec, [{ index: 7, content: 'Different evidence' }]).errors.some(e => e.includes('quote is absent')));
  assert.deepEqual(validate(spec, [{ index: 7, content: 'Input\n data' }]).errors, []);
  assert.ok(parseFigureSpec('{broken').errors.length);
});

test('quality-first settings propagate actual custom palette colors', () => {
  const colors = { primary: '#112233', secondary: '#445566' };
  const settings = withPalette({ ...DEFAULT_SETTINGS, style_preset: 'pastel', color_scheme: 'custom-id' }, [{ id: 'custom-id', type: 'custom', colors }]);
  assert.equal(settings.profile, 'quality');
  assert.equal(settings.resolution, '2K');
  assert.equal(settings.style_preset, 'pastel');
  assert.deepEqual(settings.custom_colors, colors);
  assert.equal(withPalette(DEFAULT_SETTINGS, [{ id: 'preset-okabe-ito', colors }]).color_scheme, 'preset-okabe-ito');
});

test('preset slugs resolve seeded UUID palettes and propagate their swatch colors', () => {
  const colors = { primary: '#0072B2', secondary: '#E69F00', tertiary: '#009E73', text: '#333333', fill: '#FFFFFF', section_bg: '#F7F7F7', border: '#CCCCCC', arrow: '#4D4D4D' };
  const palette = { id: '727afcef-0a5b-48ea-8b82-950173cb2d4d', slug: 'okabe-ito', type: 'preset', name: 'Okabe-Ito', colors };
  for (const value of ['okabe-ito', ' okabe-ito ', 'preset-okabe-ito', palette.id]) {
    assert.equal(findPalette([palette], value), palette);
    const resolved = withPalette({ ...DEFAULT_SETTINGS, color_scheme: value }, [palette]);
    assert.equal(resolved.color_scheme, palette.id);
    assert.deepEqual(resolved.custom_colors, colors);
  }
});

test('palette resolution keeps legacy and custom IDs, preferring exact IDs over aliases', () => {
  const legacy = { id: 'preset-okabe-ito', colors: { primary: '#0072B2' } };
  const custom = { id: 'custom-uuid', slug: null, type: 'custom', colors: { primary: '#112233' } };
  assert.equal(findPalette([legacy], 'okabe-ito'), legacy);
  assert.equal(findPalette([legacy], legacy.id), legacy);
  assert.equal(findPalette([custom], custom.id), custom);
  const exact = { ...custom, id: 'okabe-ito' };
  assert.equal(findPalette([legacy, exact], 'okabe-ito'), exact);
  assert.equal(findPalette([custom], ''), undefined);
  assert.equal(findPalette([custom], 'missing'), undefined);
  const settings = { ...DEFAULT_SETTINGS, color_scheme: 'missing', custom_colors: custom.colors };
  assert.deepEqual(withPalette(settings, [custom]), settings);
});

test('job states and image states are distinct, and retries are explicit', () => {
  assert.ok(activeStatus('generating'));
  assert.ok(activeStatus('queued'));
  assert.ok(completedStatus('completed'));
  assert.ok(!completedStatus('cancelled'));
  for (const status of ['failed', 'interrupted']) assert.ok(canRetryJob({ status }));
  for (const status of ['queued', 'running', 'succeeded', 'cancelled']) assert.ok(!canRetryJob({ status }));
});

test('images inherit a prompt palette snapshot without later preset changes overwriting it', () => {
  const colors = { primary: '#4C72B0', secondary: '#DD8452', tertiary: '#55A868', text: '#1F2937', fill: '#FFFFFF', section_bg: '#F8FAFC', border: '#CBD5E1', arrow: '#334155' };
  const prompt = { style_preset: 'pastel', suggested_aspect_ratio: '4:3', generation_metadata: { color_scheme: 'saved-palette', palette: colors, profile: 'draft' } };
  const settings = settingsForPrompt(prompt, DEFAULT_SETTINGS);
  assert.equal(settings.style_preset, 'pastel');
  assert.equal(settings.profile, 'draft');
  assert.equal(settings.aspect_ratio, '4:3');
  assert.equal(settings.color_scheme, 'saved-palette');
  assert.deepEqual(withPalette(settings, [{ id: 'saved-palette', colors: { ...colors, primary: '#000000' } }]).custom_colors, colors);
  assert.deepEqual(settingsForPrompt({ generation_metadata: null }, DEFAULT_SETTINGS), { ...DEFAULT_SETTINGS, custom_colors: undefined });
});

test('ancestry tolerates missing and cyclic legacy history', () => {
  const images = [{ id: 'a' }, { id: 'b', parent_image_id: 'a' }, { id: 'c', parent_image_id: 'b' }];
  assert.deepEqual(imageAncestors(images[2], images).map(x => x.id), ['a', 'b']);
  assert.deepEqual(imageAncestors({ id: 'a', parent_image_id: 'missing' }, images), []);
  assert.equal(imageAncestors({ id: 'a', parent_image_id: 'b' }, [{ id: 'b', parent_image_id: 'a' }]).length, 1);
});

test('source indices and blank edited prompts never silently fall back', () => {
  assert.equal(sectionIndex({ index: 19 }, 0), 19);
  assert.equal(sectionIndex({}, 3), 3);
  assert.equal(promptText({ active_prompt: '', edited_prompt: 'old' }), '');
  assert.equal(promptText({ active_prompt: null, edited_prompt: 'new' }), 'new');
});

test('provenance and API errors exclude credential fields and key strings', () => {
  const secret = 'sk-' + 'not-a-real-key';
  const clean = nonSecret({ api_key: secret, nested: { authorization: 'credential', input_tokens: 15, prompt: `never show ${secret}` } });
  assert.deepEqual(clean, { nested: { input_tokens: 15, prompt: 'never show [redacted]' } });
  const conflict = new AxiosError('request', '409', undefined, undefined, { status: 409, data: { detail: [{ msg: 'Stale revision' }] } });
  assert.equal(getApiErrorMessage(conflict, 'fallback'), 'Stale revision');
  assert.ok(isRevisionConflict(conflict));
  assert.ok(!isUnknownOutcome(conflict));
  assert.ok(isUnknownOutcome(new AxiosError('timeout')));
});

test('mask geometry stays reference-relative and uses transparent editing regions', () => {
  assert.deepEqual(maskPoint(160, 90, { left: 10, top: 15, width: 300, height: 150 }), { x: .5, y: .5 });
  assert.deepEqual(maskPoint(-1, 500, { left: 0, top: 0, width: 300, height: 150 }), { x: 0, y: 1 });
  const calls = [];
  const context = new Proxy({}, { set: (target, key, value) => { calls.push([key, value]); target[key] = value; return true; }, get: (target, key) => target[key] ?? ((...args) => calls.push([key, ...args])) });
  paintStrokes(context, 1600, 900, [{ size: .02, points: [{ x: .5, y: .5 }] }], true);
  assert.ok(calls.some(x => x[0] === 'fillRect' && x[3] === 1600 && x[4] === 900));
  assert.ok(calls.some(x => x[0] === 'globalCompositeOperation' && x[1] === 'destination-out'));
  assert.ok(calls.some(x => x[0] === 'arc' && x[1] === 800 && x[2] === 450 && x[3] === 16));
});

test('unsaved prompt drafts recover with their original revision and clear after save', () => {
  const values = new Map();
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) } });
  const base = { text: 'Saved', spec: '', revision: 2 };
  storePromptDraft('p1', { base, text: 'Unsaved', spec: '' });
  assert.equal(readPromptDraft('p1', { ...base, revision: 3 }).base.revision, 2);
  assert.equal(readPromptDraft('p1', base).text, 'Unsaved');
  assert.equal(readPromptDraft('p2', base).text, 'Saved');
  storePromptDraft('p1', { base, text: 'Saved', spec: '' });
  assert.equal(values.size, 0);
  delete globalThis.sessionStorage;
});

test('clearing an existing FigureSpec explicitly produces null, including whitespace-only drafts', () => {
  const saved = JSON.stringify(spec);
  for (const blank of ['', ' \n\t ']) {
    assert.ok(figureSpecChanged(saved, blank));
    assert.deepEqual(figureSpecPatch(saved, blank), { figure_spec: null });
  }
});

test('unchanged or originally empty FigureSpec is omitted rather than treated as deletion', () => {
  for (const [saved, draft] of [['', ''], ['', ' \n '], [' \t ', ''], [JSON.stringify(spec), JSON.stringify(spec)]]) {
    assert.equal(figureSpecChanged(saved, draft), false);
    assert.deepEqual(figureSpecPatch(saved, draft), {});
  }
  assert.deepEqual(figureSpecPatch('', JSON.stringify(spec), spec), { figure_spec: spec });
  assert.throws(() => figureSpecPatch(JSON.stringify(spec), '{invalid'), /Invalid FigureSpec/);
});

test('prompt saves serialize explicit spec deletion and omit unchanged empty values', async t => {
  const previousAdapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = previousAdapter; });
  const bodies = [];
  api.defaults.adapter = async config => {
    bodies.push(JSON.parse(config.data));
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
  };
  await workbenchApi.savePrompt('prompt', { edited_prompt: 'Unchanged prompt', expected_revision: 4, ...figureSpecPatch(JSON.stringify(spec), '') });
  await workbenchApi.savePrompt('prompt', { edited_prompt: 'Edited prompt', expected_revision: 5, ...figureSpecPatch('', '') });
  assert.equal(bodies[0].figure_spec, null);
  assert.equal(bodies[0].expected_revision, 4);
  assert.equal(Object.hasOwn(bodies[1], 'figure_spec'), false);
});

test('typed API sends revision guards, explicit document, style, palette, exports, and multipart masks', async () => {
  const requests = [];
  api.defaults.adapter = async config => {
    requests.push(config);
    return { data: { id: 'accepted', status: 'queued' }, status: 202, statusText: 'Accepted', headers: {}, config };
  };
  await workbenchApi.promptJob('project/id', { document_id: 'selected-doc', section_indices: [7], style_preset: 'pastel', idempotency_key: 'one-request' });
  assert.equal(requests[0].url, '/projects/project%2Fid/prompt-jobs');
  assert.equal(JSON.parse(requests[0].data).document_id, 'selected-doc');
  await workbenchApi.savePrompt('prompt', { edited_prompt: 'local draft', expected_revision: 4, figure_spec: spec });
  assert.equal(JSON.parse(requests[1].data).expected_revision, 4);
  await workbenchApi.directImage({ ...DEFAULT_SETTINGS, prompt: 'figure', idempotency_key: 'direct-key' });
  assert.equal(JSON.parse(requests[2].data).profile, 'quality');
  await workbenchApi.exportFigure('prompt', { width: 1600, format: 'drawio', figure_spec: spec, idempotency_key: 'export-key' });
  assert.equal(JSON.parse(requests[3].data).format, 'drawio');
  await workbenchApi.editImage('image', { instruction: 'edit', reference: new File(['reference'], 'reference.png', { type: 'image/png' }), mask: new Blob(['mask'], { type: 'image/png' }), idempotencyKey: 'edit-key' });
  const body = requests[4].data;
  assert.ok(body instanceof FormData);
  assert.equal(body.get('edit_instruction'), 'edit');
  assert.equal(body.get('reference_image').name, 'reference.png');
  assert.equal(body.get('mask_image').name, 'mask.png');
  assert.equal(body.get('idempotency_key'), 'edit-key');
  assert.equal(requests.length, 5);
});
