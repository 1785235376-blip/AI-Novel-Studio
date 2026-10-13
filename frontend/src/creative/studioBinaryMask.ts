/** Canonical mask storage is one row-major, MSB-first bit per pixel. RGBA is never persisted. */
export const BINARY_MASK_MIN_SIZE = 64;
export const BINARY_MASK_MAX_SIZE = 1024;
export const BINARY_MASK_MAX_RADIUS = 32;
export const BINARY_MASK_UNDO_LIMIT = 16;

export type SerializedBinaryMask = { bitplane_base64: string; keep_pixels: number; remove_pixels: number };
type Stroke = { before: Uint8Array; x: number; y: number; radius: number; keep: boolean; changed: boolean };

function integerInRange(value: number, minimum: number, maximum: number, name: string) {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw new Error(`${name}必须是 ${minimum}–${maximum} 之间的整数。`);
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

  clear(keep: boolean): boolean {
    this.assertIdle(); this.validateKeep(keep);
    const value = keep ? 255 : 0;
    if (this.bits.every(byte => byte === value)) return false;
    this.remember(this.bits.slice()); this.bits.fill(value); this.changeRevision++; return true;
  }

  undo(): boolean {
    this.assertIdle(); const previous = this.history.pop();
    if (!previous) return false;
    this.bits.fill(0); this.bits = previous; this.changeRevision++; return true;
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
    this.stroke?.before.fill(0); this.stroke = null; this.released = true; this.changeRevision++;
  }
}
