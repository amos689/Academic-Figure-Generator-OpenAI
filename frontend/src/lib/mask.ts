export interface MaskPoint { x: number; y: number }
export interface MaskStroke { points: MaskPoint[]; size: number }

export function maskPoint(clientX: number, clientY: number, rect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>): MaskPoint {
  return { x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)) };
}

export function paintStrokes(context: CanvasRenderingContext2D, width: number, height: number, strokes: MaskStroke[], mask: boolean) {
  context.clearRect(0, 0, width, height);
  if (mask) { context.fillStyle = '#ffffff'; context.fillRect(0, 0, width, height); }
  context.globalCompositeOperation = mask ? 'destination-out' : 'source-over';
  context.strokeStyle = mask ? '#000000' : 'rgba(239, 68, 68, 0.55)';
  context.fillStyle = context.strokeStyle;
  context.lineCap = 'round'; context.lineJoin = 'round';
  for (const stroke of strokes) {
    const first = stroke.points[0];
    if (!first) continue;
    context.lineWidth = stroke.size * width;
    context.beginPath();
    context.arc(first.x * width, first.y * height, context.lineWidth / 2, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.moveTo(first.x * width, first.y * height);
    for (const point of stroke.points.slice(1)) context.lineTo(point.x * width, point.y * height);
    context.stroke();
  }
  context.globalCompositeOperation = 'source-over';
}

export function exportMask(width: number, height: number, strokes: MaskStroke[]): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) return Promise.reject(new Error('Canvas unavailable'));
  paintStrokes(context, width, height, strokes, true);
  return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Mask export failed')), 'image/png'));
}
