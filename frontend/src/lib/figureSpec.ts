import { z } from 'zod';
import type { FigureSpec, Section } from './types';

const identifier = z.string().regex(/^[A-Za-z][A-Za-z0-9_.-]{0,63}$/);
const plain = (value: string) => !/(?:<|&lt;|&#0*60;|&#x0*3c;)\s*(?:\/?\s*[a-z]|!|\?)|(?:javascript|vbscript)\s*:|data\s*:\s*(?:text\/html|image\/svg\+xml)/i.test(value)
  && ![...value].some(char => { const n = char.codePointAt(0)!; return (n < 32 && !'\n\r\t'.includes(char)) || (n >= 127 && n <= 159) || (n >= 0xd800 && n <= 0xdfff) || (n & 0xffff) >= 0xfffe; });
const plainText = (max: number) => z.string().max(max).refine(plain, 'Raw markup, scripts, and control characters are not allowed');
const label = plainText(240);
const requiredLabel = label.refine(value => !!value.trim(), 'Label must not be blank');
const source = z.object({ section_index: z.number().int().min(0).max(100000), quote: plainText(2000).refine(value => !!value.trim(), 'Quote must not be blank') }).strict();
export const figureSpecSchema = z.object({
  version: z.literal(1), title: label, caption: plainText(4000), direction: z.enum(['LR', 'TB']),
  nodes: z.array(z.object({
    id: identifier, label: requiredLabel, role: z.enum(['input', 'process', 'output', 'note']),
    group_id: identifier.nullable().optional(), sources: z.array(source).max(16),
  }).strict()).min(1).max(100),
  edges: z.array(z.object({
    id: identifier, source: identifier, target: identifier, label, kind: z.enum(['data', 'control', 'skip']), sources: z.array(source).max(16),
  }).strict()).max(200),
  groups: z.array(z.object({ id: identifier, label: requiredLabel }).strict()).max(32),
}).strict().superRefine((spec, context) => {
  const textLength = spec.title.length + spec.caption.length + [...spec.nodes, ...spec.edges, ...spec.groups].reduce((sum, item) => sum + item.label.length, 0)
    + [...spec.nodes, ...spec.edges].reduce((sum, item) => sum + item.sources.reduce((n, ref) => n + ref.quote.length, 0), 0);
  if (textLength > 100000) context.addIssue({ code: 'custom', message: 'Total figure text exceeds 100000 characters' });
  const allIds = new Set<string>();
  for (const collection of ['nodes', 'edges', 'groups'] as const) {
    spec[collection].forEach((item, index) => {
      if (allIds.has(item.id)) context.addIssue({ code: 'custom', message: `Duplicate ID: ${item.id}`, path: [collection, index, 'id'] });
      allIds.add(item.id);
    });
  }
  const nodes = new Set(spec.nodes.map(node => node.id));
  const groups = new Set(spec.groups.map(group => group.id));
  spec.nodes.forEach((node, index) => {
    if (node.group_id && !groups.has(node.group_id)) context.addIssue({ code: 'custom', message: `Unknown group: ${node.group_id}`, path: ['nodes', index, 'group_id'] });
  });
  spec.edges.forEach((edge, index) => {
    for (const side of ['source', 'target'] as const) {
      if (!nodes.has(edge[side])) context.addIssue({ code: 'custom', message: `Unknown node: ${edge[side]}`, path: ['edges', index, side] });
    }
  });
});

export function parseFigureSpec(text: string, sections?: Section[]): { spec?: FigureSpec; errors: string[] } {
  let value: unknown;
  try { value = JSON.parse(text); } catch { return { errors: ['Invalid JSON'] }; }
  const result = figureSpecSchema.safeParse(value);
  if (!result.success) return { errors: result.error.issues.map(issue => `${issue.path.join('.')}: ${issue.message}`) };
  if (sections) {
    const byIndex = new Map(sections.map((section, index) => [section.index ?? index, section]));
    const normalize = (text: string) => text.replace(/\s+/g, ' ').trim();
    const errors = [...result.data.nodes, ...result.data.edges].flatMap(item => item.sources.flatMap(ref => {
      const section = byIndex.get(ref.section_index);
      if (!section) return [`${item.id}: unknown section ${ref.section_index}`];
      const content = section.content ?? section.text;
      if (content && !normalize(content).includes(normalize(ref.quote))) return [`${item.id}: quote is absent from section ${ref.section_index}`];
      return [];
    }));
    if (errors.length) return { errors };
  }
  return { spec: result.data, errors: [] };
}
