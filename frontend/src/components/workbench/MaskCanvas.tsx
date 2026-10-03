import { useEffect, useRef, useState } from 'react';
import { Paintbrush, RotateCcw, Undo2 } from 'lucide-react';
import type { MaskStroke } from '../../lib/mask';
import { maskPoint, paintStrokes } from '../../lib/mask';
import { useI18n } from '../../lib/i18n';
import { ErrorNotice, Field, IconButton } from './Common';

export function MaskCanvas({ url, onChange, disabled }: {
  url: string; onChange: (width: number, height: number, strokes: MaskStroke[]) => void; disabled: boolean;
}) {
  const { t } = useI18n();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState(30);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [strokes, setStrokes] = useState<MaskStroke[]>([]);
  const [error, setError] = useState('');
  const drawing = useRef<MaskStroke | null>(null);
  const draw = (values: MaskStroke[]) => {
    const context = canvas.current?.getContext('2d');
    if (context) paintStrokes(context, dimensions.width, dimensions.height, values, false);
  };
  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (context) paintStrokes(context, dimensions.width, dimensions.height, strokes, false);
    onChange(dimensions.width, dimensions.height, strokes);
  }, [dimensions, strokes, onChange]);
  const finish = () => {
    const stroke = drawing.current;
    drawing.current = null;
    if (stroke) setStrokes(previous => [...previous, stroke]);
  };
  return <div className="space-y-3">
    <div className="flex flex-wrap items-end gap-3"><Paintbrush className="mb-2 h-4 w-4 shrink-0 text-red-600" />
      <div className="min-w-0 flex-1"><Field label={`${t('Brush size', '画笔大小')} · ${size}`}><input type="range" min={4} max={100} value={size} onChange={e => setSize(Number(e.target.value))} disabled={disabled} /></Field></div>
      <IconButton label={t('Undo stroke', '撤销笔画')} disabled={disabled || !strokes.length} onClick={() => setStrokes(previous => previous.slice(0, -1))}><Undo2 className="h-4 w-4" /></IconButton>
      <IconButton label={t('Clear mask', '清除蒙版')} disabled={disabled || !strokes.length} onClick={() => setStrokes([])}><RotateCcw className="h-4 w-4" /></IconButton>
    </div>
    <ErrorNotice message={error} />
    <div className="relative mx-auto w-full overflow-hidden border bg-white" style={dimensions.width ? { aspectRatio: `${dimensions.width} / ${dimensions.height}` } : undefined}>
      <img src={url} alt={t('Edit reference', '编辑参考图')} className="block h-auto w-full" draggable={false} onLoad={e => {
        const { naturalWidth: width, naturalHeight: height } = e.currentTarget;
        if (!width || !height || width * height > 32_000_000) { setError(t('Reference dimensions are unsupported (maximum 32 megapixels).', '参考图尺寸不支持（最多 3200 万像素）。')); return; }
        setDimensions({ width, height });
      }} onError={() => setError(t('Invalid reference image.', '参考图无法读取。'))} />
      {!!dimensions.width && <canvas ref={canvas} width={dimensions.width} height={dimensions.height} className={`absolute inset-0 h-full w-full touch-none ${disabled ? '' : 'cursor-crosshair'}`} role="img" aria-label={t('Mask drawing canvas', '蒙版绘制画布')}
        onPointerDown={e => {
          if (disabled || e.button !== 0) return;
          const rect = e.currentTarget.getBoundingClientRect();
          e.currentTarget.setPointerCapture(e.pointerId);
          drawing.current = { size: size / rect.width, points: [maskPoint(e.clientX, e.clientY, rect)] };
          draw([...strokes, drawing.current]);
        }}
        onPointerMove={e => { if (drawing.current) { drawing.current.points.push(maskPoint(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect())); draw([...strokes, drawing.current]); } }}
        onPointerUp={finish} onPointerCancel={finish} onLostPointerCapture={finish} />}
    </div>
    <p className="text-xs text-muted-foreground">{t('Red: editable area. Unmasked regions may still change.', '红色：编辑区域。未标记区域仍可能发生变化。')} {dimensions.width ? `${dimensions.width} × ${dimensions.height}` : ''}</p>
  </div>;
}
