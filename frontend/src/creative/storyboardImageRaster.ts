/**
 * Conservative, read-only admission before handing an approved thumbnail to a
 * native decoder. This checks containers and allocation bounds, not the encoded
 * pixels: callers must still handle decode failure and verify decoded dimensions.
 * Unsupported profiles are rejected intact, never stripped or rewritten.
 */
const MAX_BYTES = 8 * 1024 * 1024;
const MAX_SIDE = 4096;
const MAX_PIXELS = 4_194_304;
const MAX_RECORDS = 1024;
type Dimensions = { width: number; height: number };

function invalid(format: string): never {
  throw new Error(`${format} has an invalid or unsupported static image structure.`);
}

function metadata(format: string): never {
  throw new Error(`${format} metadata or animation is not supported for a safe preview.`);
}

function dimensions(width: number, height: number): Dimensions {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1
    || width > MAX_SIDE || height > MAX_SIDE || width * height > MAX_PIXELS) {
    throw new Error('Image dimensions exceed the preview limit (4096 per side, 4194304 pixels).');
  }
  return { width, height };
}

const be16 = (b: Uint8Array, p: number) => b[p] * 256 + b[p + 1];
const le16 = (b: Uint8Array, p: number) => b[p] + b[p + 1] * 256;
const be32 = (b: Uint8Array, p: number) => (b[p] * 0x1000000 + b[p + 1] * 0x10000 + b[p + 2] * 256 + b[p + 3]);
const le24 = (b: Uint8Array, p: number) => b[p] + b[p + 1] * 256 + b[p + 2] * 0x10000;
const le32 = (b: Uint8Array, p: number) => le24(b, p) + b[p + 3] * 0x1000000;
const tag = (b: Uint8Array, p: number) => String.fromCharCode(b[p], b[p + 1], b[p + 2], b[p + 3]);

const CRC_TABLE = Uint32Array.from({ length: 256 }, (_, value) => {
  for (let bit = 0; bit < 8; bit++) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});

function crc32(bytes: Uint8Array, start: number, end: number): number {
  let crc = 0xffffffff;
  for (let p = start; p < end; p++) crc = CRC_TABLE[(crc ^ bytes[p]) & 255] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function inspectPng(bytes: Uint8Array): Dimensions {
  if (bytes.length < 8 || [137, 80, 78, 71, 13, 10, 26, 10].some((value, i) => bytes[i] !== value)) invalid('PNG');
  let result: Dimensions | undefined;
  let depth = 0, color = 0, paletteEntries = 0, idatBytes = 0, records = 0;
  let idatStarted = false, idatEnded = false;
  const seen = new Set<string>();
  const zlibHeader: number[] = [];
  for (let offset = 8; offset < bytes.length;) {
    if (++records > MAX_RECORDS || bytes.length - offset < 12) invalid('PNG');
    const length = be32(bytes, offset), kind = tag(bytes, offset + 4);
    const start = offset + 8, end = start + length;
    if (length > bytes.length - offset - 12 || crc32(bytes, offset + 4, end) !== be32(bytes, end)) invalid('PNG');
    if (!result && kind !== 'IHDR') invalid('PNG');
    if (kind !== 'IDAT' && idatStarted) idatEnded = true;
    if (kind !== 'IDAT' && seen.has(kind)) invalid('PNG');
    switch (kind) {
      case 'IHDR': {
        if (offset !== 8 || length !== 13) invalid('PNG');
        result = dimensions(be32(bytes, start), be32(bytes, start + 4));
        depth = bytes[start + 8]; color = bytes[start + 9];
        const depths: Record<number, number[]> = { 0: [1, 2, 4, 8, 16], 2: [8, 16], 3: [1, 2, 4, 8], 4: [8, 16], 6: [8, 16] };
        // Interlacing is deliberately outside this thumbnail admission profile.
        if (!depths[color]?.includes(depth) || bytes[start + 10] !== 0 || bytes[start + 11] !== 0 || bytes[start + 12] !== 0) invalid('PNG');
        break;
      }
      case 'PLTE':
        if (idatStarted || seen.has('tRNS') || color === 0 || color === 4 || length < 3 || length > 768 || length % 3 !== 0) invalid('PNG');
        paletteEntries = length / 3;
        if (color === 3 && paletteEntries > 2 ** depth) invalid('PNG');
        break;
      case 'tRNS':
        if (idatStarted) invalid('PNG');
        if (color === 3) {
          if (!paletteEntries || length < 1 || length > paletteEntries) invalid('PNG');
        } else if (color === 0 || color === 2) {
          if (length !== (color === 0 ? 2 : 6)) invalid('PNG');
          for (let p = start; p < end; p += 2) if (be16(bytes, p) >= 2 ** depth) invalid('PNG');
        } else invalid('PNG');
        break;
      case 'gAMA':
      case 'cHRM':
      case 'sRGB':
        if (idatStarted || seen.has('PLTE')) invalid('PNG');
        if (kind === 'gAMA' && (length !== 4 || be32(bytes, start) === 0)) invalid('PNG');
        if (kind === 'cHRM' && length !== 32) invalid('PNG');
        if (kind === 'sRGB' && (length !== 1 || bytes[start] > 3)) invalid('PNG');
        break;
      case 'pHYs':
        if (idatStarted || length !== 9 || bytes[start + 8] > 1) invalid('PNG');
        break;
      case 'IDAT':
        if (idatEnded || (color === 3 && !paletteEntries)) invalid('PNG');
        idatStarted = true; idatBytes += length;
        for (let p = start; p < end && zlibHeader.length < 2; p++) zlibHeader.push(bytes[p]);
        break;
      case 'IEND':
        if (length !== 0 || end + 4 !== bytes.length || idatBytes < 6 || !result) invalid('PNG');
        // Deflate only, bounded zlib window, valid check bits, no preset dictionary.
        if ((zlibHeader[0] & 15) !== 8 || (zlibHeader[0] >>> 4) > 7 || (zlibHeader[1] & 32) !== 0
          || (zlibHeader[0] * 256 + zlibHeader[1]) % 31 !== 0) invalid('PNG');
        return result;
      default:
        // Includes APNG, compressed text, ICC profiles and unknown ancillary data.
        metadata('PNG');
    }
    seen.add(kind);
    offset = end + 4;
  }
  return invalid('PNG');
}

type JpegComponent = { id: number; quantization: number };

function inspectJpeg(bytes: Uint8Array): Dimensions {
  if (bytes.length < 4 || bytes[0] !== 255 || bytes[1] !== 0xd8) invalid('JPEG');
  let result: Dimensions | undefined;
  const components: JpegComponent[] = [];
  const quantizationTables = new Set<number>(), huffmanTables = new Set<number>();
  let jfif = false, restartInterval: number | undefined, records = 0;
  for (let offset = 2; offset < bytes.length;) {
    if (++records > MAX_RECORDS || bytes[offset] !== 255) invalid('JPEG');
    // A closed profile: no repeated marker fill bytes outside entropy data.
    const marker = bytes[offset + 1];
    if (offset + 4 > bytes.length || marker === 0 || marker === 255) invalid('JPEG');
    const length = be16(bytes, offset + 2), start = offset + 4, end = offset + 2 + length;
    if (length < 2 || end > bytes.length) invalid('JPEG');
    if (marker === 0xe0) {
      // Ordinary JFIF only; embedded thumbnails, JFXX and every other APP profile
      // (EXIF orientation, ICC, MPF and Adobe included) are not silently modified.
      if (jfif || offset !== 2 || length !== 16 || tag(bytes, start) !== 'JFIF' || bytes[start + 4] !== 0
        || bytes[start + 5] !== 1 || bytes[start + 6] > 2 || bytes[start + 7] > 2
        || be16(bytes, start + 8) === 0 || be16(bytes, start + 10) === 0
        || bytes[start + 12] !== 0 || bytes[start + 13] !== 0) metadata('JPEG');
      jfif = true;
    } else if ((marker >= 0xe1 && marker <= 0xef) || marker === 0xfe) {
      metadata('JPEG');
    } else if (marker === 0xdb) {
      let p = start;
      while (p < end) {
        const table = bytes[p++];
        if (table > 3 || quantizationTables.has(table) || end - p < 64) invalid('JPEG');
        for (let i = 0; i < 64; i++) if (bytes[p + i] === 0) invalid('JPEG');
        quantizationTables.add(table); p += 64;
      }
      if (p === start) invalid('JPEG');
    } else if (marker === 0xc4) {
      let p = start;
      while (p < end) {
        const table = bytes[p++];
        if ((table & 0xec) !== 0 || huffmanTables.has(table) || end - p < 16) invalid('JPEG');
        let count = 0, slots = 1;
        for (let i = 0; i < 16; i++) {
          const atLength = bytes[p++]; count += atLength; slots = slots * 2 - atLength;
          // JPEG must not assign the all-ones code, nor oversubscribe the tree.
          if (slots <= 0) invalid('JPEG');
        }
        if (count < 1 || count > 256 || count > end - p) invalid('JPEG');
        const values = new Set<number>();
        for (let i = 0; i < count; i++) {
          const value = bytes[p++];
          if (values.has(value)) invalid('JPEG');
          values.add(value);
          if (table < 16 ? value > 11 : (value & 15) > 10 || ((value & 15) === 0 && value !== 0 && value !== 0xf0)) invalid('JPEG');
        }
        huffmanTables.add(table);
      }
      if (p === start) invalid('JPEG');
    } else if (marker === 0xc0) {
      if (result || length < 11 || bytes[start] !== 8) invalid('JPEG');
      const count = bytes[start + 5];
      if ((count !== 1 && count !== 3) || length !== 8 + 3 * count) invalid('JPEG');
      result = dimensions(be16(bytes, start + 3), be16(bytes, start + 1));
      const ids = new Set<number>();
      let blocks = 0;
      for (let p = start + 6; p < end; p += 3) {
        const id = bytes[p], horizontal = bytes[p + 1] >>> 4, vertical = bytes[p + 1] & 15, quantization = bytes[p + 2];
        if (ids.has(id) || horizontal < 1 || horizontal > 4 || vertical < 1 || vertical > 4 || quantization > 3) invalid('JPEG');
        ids.add(id); blocks += horizontal * vertical; components.push({ id, quantization });
      }
      if (blocks > 10) invalid('JPEG');
    } else if (marker === 0xdd) {
      if (restartInterval !== undefined || length !== 4) invalid('JPEG');
      restartInterval = be16(bytes, start);
    } else if (marker === 0xda) {
      if (!result || length !== 6 + 2 * components.length || bytes[start] !== components.length) invalid('JPEG');
      for (let i = 0; i < components.length; i++) {
        const component = components[i], selectors = bytes[start + 2 + i * 2];
        if (bytes[start + 1 + i * 2] !== component.id || !quantizationTables.has(component.quantization)
          || !huffmanTables.has(selectors >>> 4) || !huffmanTables.has(16 + (selectors & 15))) invalid('JPEG');
      }
      if (bytes[end - 3] !== 0 || bytes[end - 2] !== 63 || bytes[end - 1] !== 0) invalid('JPEG');
      let entropyBytes = 0, restart = 0;
      for (let p = end; p < bytes.length;) {
        if (bytes[p++] !== 255) { entropyBytes++; continue; }
        if (p >= bytes.length) invalid('JPEG');
        const next = bytes[p++];
        if (next === 0) { entropyBytes++; continue; }
        if (next >= 0xd0 && next <= 0xd7) {
          if (!restartInterval || !entropyBytes || next !== 0xd0 + restart) invalid('JPEG');
          restart = (restart + 1) % 8; entropyBytes = 0;
        } else if (next === 0xd9 && entropyBytes > 0 && p === bytes.length) {
          return result;
        } else invalid('JPEG');
      }
      invalid('JPEG');
    } else {
      // Baseline sequential, single interleaved scan only. No DNL, hierarchical,
      // arithmetic, progressive, lossless or additional dimension-bearing frame.
      invalid('JPEG');
    }
    offset = end;
  }
  return invalid('JPEG');
}

function inspectWebp(bytes: Uint8Array): Dimensions {
  if (bytes.length < 20 || tag(bytes, 0) !== 'RIFF' || tag(bytes, 8) !== 'WEBP' || le32(bytes, 4) !== bytes.length - 8) invalid('WebP');
  let canvas: Dimensions | undefined, result: Dimensions | undefined;
  let alphaFlag = false, alphaChunk = false, records = 0;
  for (let offset = 12; offset < bytes.length;) {
    if (++records > 3 || bytes.length - offset < 8 || result) invalid('WebP');
    const kind = tag(bytes, offset), length = le32(bytes, offset + 4), start = offset + 8, end = start + length;
    const paddedEnd = end + length % 2;
    if (length > bytes.length - start || paddedEnd > bytes.length || (length % 2 && bytes[end] !== 0)) invalid('WebP');
    if (kind === 'VP8X') {
      if (offset !== 12 || canvas || length !== 10) invalid('WebP');
      const flags = bytes[start];
      if ((flags & ~0x10) !== 0) metadata('WebP');
      if (bytes[start + 1] !== 0 || bytes[start + 2] !== 0 || bytes[start + 3] !== 0) invalid('WebP');
      alphaFlag = !!(flags & 0x10);
      canvas = dimensions(le24(bytes, start + 4) + 1, le24(bytes, start + 7) + 1);
    } else if (kind === 'ALPH') {
      if (!canvas || !alphaFlag || alphaChunk || length < 2) invalid('WebP');
      const header = bytes[start], compression = header & 3;
      if (header >>> 6 !== 0 || (header >>> 4 & 3) > 1 || compression > 1) invalid('WebP');
      if (compression === 0 && length !== 1 + canvas.width * canvas.height) invalid('WebP');
      alphaChunk = true;
    } else if (kind === 'VP8 ') {
      if (length < 11 || (alphaFlag !== alphaChunk)) invalid('WebP');
      const frame = le24(bytes, start), firstPartitionLength = frame >>> 5;
      if ((frame & 1) !== 0 || ((frame >>> 1) & 7) > 3 || (frame & 16) === 0
        || bytes[start + 3] !== 0x9d || bytes[start + 4] !== 1 || bytes[start + 5] !== 0x2a
        || firstPartitionLength === 0 || firstPartitionLength > length - 10) invalid('WebP');
      const rawWidth = le16(bytes, start + 6), rawHeight = le16(bytes, start + 8);
      if (rawWidth >>> 14 !== 0 || rawHeight >>> 14 !== 0) invalid('WebP');
      result = dimensions(rawWidth, rawHeight);
    } else if (kind === 'VP8L') {
      if (length < 6 || alphaChunk || bytes[start] !== 0x2f) invalid('WebP');
      const header = le32(bytes, start + 1);
      if (header >>> 29 !== 0) invalid('WebP');
      if (canvas && alphaFlag !== !!(header & 0x10000000)) invalid('WebP');
      result = dimensions((header & 0x3fff) + 1, ((header >>> 14) & 0x3fff) + 1);
    } else metadata('WebP');
    if (result && canvas && (result.width !== canvas.width || result.height !== canvas.height)) invalid('WebP');
    offset = paddedEnd;
  }
  if (!result) invalid('WebP');
  return result;
}

export function inspectStoryboardRaster(bytes: Uint8Array, mime: string): Dimensions {
  if (bytes.byteLength > MAX_BYTES) throw new Error('Image exceeds the 8 MiB preview limit.');
  switch (mime) {
    case 'image/png': return inspectPng(bytes);
    case 'image/jpeg': return inspectJpeg(bytes);
    case 'image/webp': return inspectWebp(bytes);
    default: throw new Error('Preview supports only static PNG, JPEG, and WebP images.');
  }
}
