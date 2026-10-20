/** Canonical mask storage is one row-major, MSB-first bit per pixel. RGBA is never persisted. */
export const BINARY_MASK_MIN_SIZE = 64;
export const BINARY_MASK_MAX_SIZE = 1024;
export const BINARY_MASK_MAX_RADIUS = 32;
export const BINARY_MASK_UNDO_LIMIT = 16;
export const BINARY_MASK_POLYGON_MAX_VERTICES = 32;
export type BinaryMaskPoint = Readonly<{ x: number; y: number }>;
export type BinaryMaskPolygonPreview = Readonly<{ vertices: readonly BinaryMaskPoint[]; selected_pixels: number }>;

export type SerializedBinaryMask = { bitplane_base64: string; keep_pixels: number; remove_pixels: number };
type Stroke = { before: Uint8Array; x: number; y: number; radius: number; keep: boolean; changed: boolean };

function integerInRange(value: number, minimum: number, maximum: number, name: string) {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw new Error(`${name}必须是 ${minimum}–${maximum} 之间的整数。`);
}

const cross = (a: BinaryMaskPoint, b: BinaryMaskPoint, c: BinaryMaskPoint) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
const onSegment = (a: BinaryMaskPoint, b: BinaryMaskPoint, p: BinaryMaskPoint) => cross(a, b, p) === 0 && p.x >= Math.min(a.x, b.x) && p.x <= Math.max(a.x, b.x) && p.y >= Math.min(a.y, b.y) && p.y <= Math.max(a.y, b.y);
function intersects(a: BinaryMaskPoint, b: BinaryMaskPoint, c: BinaryMaskPoint, d: BinaryMaskPoint) {
  const abC = cross(a, b, c), abD = cross(a, b, d), cdA = cross(c, d, a), cdB = cross(c, d, b);
  return abC * abD < 0 && cdA * cdB < 0 || onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b);
}
/** Pixel centers on the boundary are included; no antialiasing or implicit clipping. */
function polygonSpans(vertices: readonly BinaryMaskPoint[], width: number, height: number): { vertices: readonly BinaryMaskPoint[]; spans: [number, number, number][] } {
  if (!Array.isArray(vertices) || vertices.length < 3 || vertices.length > BINARY_MASK_POLYGON_MAX_VERTICES) throw new Error('多边形须有 3–32 个按轮廓排序的顶点。');
  const points = vertices.map(point => {
    if (!point || typeof point !== 'object') throw new Error('多边形顶点无效。');
    integerInRange(point.x, 0, width, '顶点 X'); integerInRange(point.y, 0, height, '顶点 Y');
    return Object.freeze({ x: point.x, y: point.y });
  });
  const count = points.length;
  if (new Set(points.map(point => `${point.x},${point.y}`)).size !== count) throw new Error('多边形顶点不能重复；闭合边由预览自动连接。');
  for (let i = 0; i < count; i++) {
    const a = points[i], b = points[(i + 1) % count], c = points[(i + 2) % count];
    if (cross(a, b, c) === 0 && (b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y) < 0) throw new Error('多边形存在退化的折返边。');
    for (let j = i + 1; j < count; j++) {
      if (j === i + 1 || i === 0 && j === count - 1) continue;
      if (intersects(a, b, points[j], points[(j + 1) % count])) throw new Error('多边形不能自交或让非相邻边相触。');
    }
  }
  if (points.reduce((area, point, i) => area + point.x * points[(i + 1) % count].y - points[(i + 1) % count].x * point.y, 0) === 0) throw new Error('多边形面积为零，不能填充退化选区。');
  const spans: [number, number, number][] = [];
  const minimumY = Math.min(...points.map(point => point.y)), maximumY = Math.max(...points.map(point => point.y));
  for (let y = minimumY; y < maximumY; y++) {
    const center = y + 0.5, hits: { numerator: number; denominator: number }[] = [];
    for (let i = 0; i < count; i++) {
      const a = points[i], b = points[(i + 1) % count];
      if ((a.y > center) !== (b.y > center)) {
        // Exact integer fractions preserve the inclusive half-pixel boundary rule.
        const direction = Math.sign(b.y - a.y);
        hits.push({ numerator: direction * (2 * a.x * (b.y - a.y) + (2 * y + 1 - 2 * a.y) * (b.x - a.x)), denominator: 2 * Math.abs(b.y - a.y) });
      }
    }
    hits.sort((a, b) => a.numerator * b.denominator - b.numerator * a.denominator);
    for (let i = 0; i < hits.length; i += 2) {
      const a = hits[i], b = hits[i + 1];
      const left = Math.ceil((2 * a.numerator - a.denominator) / (2 * a.denominator)), right = Math.floor((2 * b.numerator - b.denominator) / (2 * b.denominator));
      if (left <= right) spans.push([y, left, right]);
    }
  }
  return { vertices: Object.freeze(points), spans };
}

// A small portable encoder avoids spreading a maximum-size bitplane onto the stack.
function base64(bytes: Uint8Array): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  const parts: string[] = [];
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index], second = bytes[index + 1] ?? 0, third = bytes[index + 2] ?? 0;
    parts.push(alphabet[first >>> 2], alphabet[((first & 3) << 4) | (second >>> 4)],
      index + 1 < bytes.length ? alphabet[((second & 15) << 2) | (third >>> 6)] : '=',
      index + 2 < bytes.length ? alphabet[third & 63] : '=');
  }
  return parts.join('');
}

/** A bounded local draft. All-white KEEP is intentionally valid until save/serialize. */
export class BinaryMaskDraft {
  readonly width: number;
  readonly height: number;
  private bits: Uint8Array;
  private history: Uint8Array[] = [];
  // Undo/redo transfer owned bitplanes; together they retain at most 16 states.
  private future: Uint8Array[] = [];
  private stroke: Stroke | null = null;
  private released = false;
  private changeRevision = 0;

  constructor(width: number, height: number) {
    for (const [name, size] of [['宽度', width], ['高度', height]] as const) {
      integerInRange(size, BINARY_MASK_MIN_SIZE, BINARY_MASK_MAX_SIZE, name);
      if (size % 8 !== 0) throw new Error(`${name}必须是 8 的倍数。`);
    }
    this.width = width; this.height = height;
    this.bits = new Uint8Array(width * height / 8).fill(255);
  }

  get revision() { return this.changeRevision; }
  get activeStroke() { return this.stroke !== null; }
  get canUndo() { return !this.released && this.history.length > 0; }
  get canRedo() { return !this.released && this.future.length > 0; }

  private assertAvailable() { if (this.released) throw new Error('蒙版草稿已释放，请重新读取来源。'); }
  private assertIdle() {
    this.assertAvailable();
    if (this.stroke) throw new Error('请先完成或取消当前笔画。');
  }
  private validatePoint(x: number, y: number) {
    integerInRange(x, 0, this.width - 1, 'X'); integerInRange(y, 0, this.height - 1, 'Y');
  }
  private validateKeep(keep: boolean) { if (typeof keep !== 'boolean') throw new Error('蒙版操作必须明确指定 KEEP 或 REMOVE。'); }
  private remember(before: Uint8Array) {
    // Only a committed pixel change branches history. No-ops and cancelled
    // strokes retain redo, and abandoned states are explicitly released.
    this.future.forEach(state => state.fill(0)); this.future = [];
    if (this.history.length === BINARY_MASK_UNDO_LIMIT) this.history.shift()?.fill(0);
    this.history.push(before);
  }
  private set(x: number, y: number, keep: boolean): boolean {
    const pixel = y * this.width + x, byte = pixel >>> 3, bit = 1 << (7 - (pixel & 7));
    const value = keep ? this.bits[byte] | bit : this.bits[byte] & ~bit;
    if (this.bits[byte] === value) return false;
    this.bits[byte] = value; return true;
  }
  private stamp(x: number, y: number, radius: number, keep: boolean): boolean {
    let changed = false;
    for (let row = Math.max(0, y - radius); row <= Math.min(this.height - 1, y + radius); row++) {
      const span = Math.floor(Math.sqrt(radius * radius - (row - y) * (row - y)));
      for (let column = Math.max(0, x - span); column <= Math.min(this.width - 1, x + span); column++) {
        changed = this.set(column, row, keep) || changed;
      }
    }
    return changed;
  }

  get(x: number, y: number): boolean {
    this.assertAvailable(); this.validatePoint(x, y);
    const pixel = y * this.width + x;
    return (this.bits[pixel >>> 3] & (1 << (7 - (pixel & 7)))) !== 0;
  }
  snapshot(): Uint8Array { this.assertAvailable(); return this.bits.slice(); }

  beginStroke(x: number, y: number, radius: number, keep: boolean): boolean {
    this.assertIdle(); this.validatePoint(x, y);
    integerInRange(radius, 0, BINARY_MASK_MAX_RADIUS, '笔刷半径'); this.validateKeep(keep);
    const before = this.bits.slice(), changed = this.stamp(x, y, radius, keep);
    this.stroke = { before, x, y, radius, keep, changed };
    if (changed) this.changeRevision++;
    return changed;
  }

  moveStroke(x: number, y: number): boolean {
    this.assertAvailable(); this.validatePoint(x, y);
    const stroke = this.stroke;
    if (!stroke) throw new Error('当前没有进行中的笔画。');
    // Integer endpoints are bounded to the image; this loop can run at most 1024 times.
    const dx = Math.abs(x - stroke.x), dy = Math.abs(y - stroke.y);
    const sx = stroke.x < x ? 1 : -1, sy = stroke.y < y ? 1 : -1;
    let column = stroke.x, row = stroke.y, error = dx - dy, changed = false;
    for (let step = 0; step < BINARY_MASK_MAX_SIZE; step++) {
      changed = this.stamp(column, row, stroke.radius, stroke.keep) || changed;
      if (column === x && row === y) break;
      const doubled = error * 2;
      if (doubled > -dy) { error -= dy; column += sx; }
      if (doubled < dx) { error += dx; row += sy; }
    }
    stroke.x = x; stroke.y = y; stroke.changed ||= changed;
    if (changed) this.changeRevision++;
    return changed;
  }

  commitStroke(): boolean {
    this.assertAvailable();
    const stroke = this.stroke; if (!stroke) return false;
    this.stroke = null;
    if (stroke.changed) this.remember(stroke.before); else stroke.before.fill(0);
    return stroke.changed;
  }

  cancelStroke(): boolean {
    this.assertAvailable();
    const stroke = this.stroke; if (!stroke) return false;
    this.stroke = null;
    if (stroke.changed) { this.bits.fill(0); this.bits = stroke.before; this.changeRevision++; }
    else stroke.before.fill(0);
    return stroke.changed;
  }

  paint(x: number, y: number, radius: number, keep: boolean): boolean {
    this.beginStroke(x, y, radius, keep); return this.commitStroke();
  }

  rectangle(x: number, y: number, width: number, height: number, keep: boolean): boolean {
    this.assertIdle(); this.validatePoint(x, y); this.validateKeep(keep);
    integerInRange(width, 1, this.width, '矩形宽度'); integerInRange(height, 1, this.height, '矩形高度');
    if (x + width > this.width || y + height > this.height) throw new Error('矩形超出蒙版边界；请明确修改 X、Y、宽度或高度，不会自动裁剪。');
    const before = this.bits.slice(); let changed = false;
    for (let row = y; row < y + height; row++) {
      for (let column = x; column < x + width; column++) changed = this.set(column, row, keep) || changed;
    }
    if (changed) { this.remember(before); this.changeRevision++; } else before.fill(0);
    return changed;
  }

  previewPolygon(vertices: readonly BinaryMaskPoint[]): BinaryMaskPolygonPreview {
    this.assertIdle(); const selected = polygonSpans(vertices, this.width, this.height);
    return Object.freeze({ vertices: selected.vertices, selected_pixels: selected.spans.reduce((total, [, left, right]) => total + right - left + 1, 0) });
  }

  polygon(vertices: readonly BinaryMaskPoint[], keep: boolean): boolean {
    this.assertIdle(); this.validateKeep(keep);
    const selected = polygonSpans(vertices, this.width, this.height), before = this.bits.slice(); let changed = false;
    for (const [y, left, right] of selected.spans) for (let x = left; x <= right; x++) changed = this.set(x, y, keep) || changed;
    if (changed) { this.remember(before); this.changeRevision++; } else before.fill(0);
    return changed;
  }

  clear(keep: boolean): boolean {
    this.assertIdle(); this.validateKeep(keep);
    const value = keep ? 255 : 0;
    if (this.bits.every(byte => byte === value)) return false;
    this.remember(this.bits.slice()); this.bits.fill(value); this.changeRevision++; return true;
  }

  undo(): boolean {
    this.assertIdle(); const previous = this.history.pop();
    if (!previous) return false;
    this.future.push(this.bits); this.bits = previous; this.changeRevision++; return true;
  }

  redo(): boolean {
    this.assertIdle(); const next = this.future.pop();
    if (!next) return false;
    this.history.push(this.bits); this.bits = next; this.changeRevision++; return true;
  }

  serialize(): SerializedBinaryMask {
    this.assertIdle(); let keep_pixels = 0;
    for (let value of this.bits) {
      value -= (value >>> 1) & 0x55;
      value = (value & 0x33) + ((value >>> 2) & 0x33);
      keep_pixels += (value + (value >>> 4)) & 0x0f;
    }
    const remove_pixels = this.width * this.height - keep_pixels;
    if (!keep_pixels || !remove_pixels) throw new Error('保存前蒙版必须同时包含白色 KEEP 和黑色 REMOVE 像素。');
    return { bitplane_base64: base64(this.bits), keep_pixels, remove_pixels };
  }

  dispose() {
    if (this.released) return;
    this.bits.fill(0); this.bits = new Uint8Array(0);
    this.history.forEach(state => state.fill(0)); this.history = [];
    this.future.forEach(state => state.fill(0)); this.future = [];
    this.stroke?.before.fill(0); this.stroke = null; this.released = true; this.changeRevision++;
  }
}
