import { Buffer } from 'node:buffer';
import { deflateSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { inspectStoryboardRaster } from './storyboardImageRaster';

// Real, deterministic 3x2 encoded images generated with Pillow 12.3. These tests
// exercise admission only; they do not execute or assert a browser/native decode.
const fromBase64 = (value: string) => Uint8Array.from(Buffer.from(value, 'base64'));
const PNG = fromBase64('iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAYAAACddGYaAAAAE0lEQVR4nGMUsUlpYIACJgYkAAAb3gE4TuR+ggAAAABJRU5ErkJggg==');
const JPEG = fromBase64('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAMDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDzSiiivYPLP//Z');
const WEBP_LOSSY = fromBase64('UklGRjQAAABXRUJQVlA4ICgAAACQAQCdASoDAAIAAUAmJZACdLoAA5gA/vi1F/quTsT44f3NjnFshgAA');
const WEBP_LOSSLESS = fromBase64('UklGRh4AAABXRUJQVlA4TBEAAAAvAkAAEAdQnlKUrICBiOh/AAA=');
const WEBP_ALPHA = fromBase64('UklGRlYAAABXRUJQVlA4WAoAAAAQAAAAAgAAAQAAQUxQSAcAAAAAgICAgICAAFZQOCAoAAAAkAEAnQEqAwACAAFAJiWQAnS6AAOYAP74tRf6rk7E+OH9zY5xbIYAAA==');
const fixtures = [
  ['PNG', PNG, 'image/png'], ['JPEG', JPEG, 'image/jpeg'],
  ['lossy WebP', WEBP_LOSSY, 'image/webp'], ['lossless WebP', WEBP_LOSSLESS, 'image/webp'],
  ['alpha WebP', WEBP_ALPHA, 'image/webp'],
] as const;

function join(...parts: Uint8Array[]): Uint8Array {
  const result = new Uint8Array(parts.reduce((total, part) => total + part.length, 0));
  let p = 0;
  for (const part of parts) { result.set(part, p); p += part.length; }
  return result;
}
const ascii = (value: string) => Uint8Array.from([...value].map(char => char.charCodeAt(0)));
const be32 = (value: number) => Uint8Array.of(value >>> 24, value >>> 16, value >>> 8, value);
const le32 = (value: number) => Uint8Array.of(value, value >>> 8, value >>> 16, value >>> 24);
function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function pngChunk(kind: string, data: Uint8Array = new Uint8Array()) {
  const body = join(ascii(kind), data);
  return join(be32(data.length), body, be32(crc32(body)));
}
const pngAfterHeader = (chunk: Uint8Array) => join(PNG.slice(0, 33), chunk, PNG.slice(33));
function pngWithHeader(width: number, height: number, color = 6, depth = 8) {
  return join(PNG.slice(0, 8), pngChunk('IHDR', join(be32(width), be32(height), Uint8Array.of(depth, color, 0, 0, 0))), PNG.slice(33));
}
function validPng(width: number, height: number) {
  const header = pngWithHeader(width, height).slice(0, 33);
  // Zero filter bytes and zero RGBA pixels, a complete real zlib pixel stream.
  return join(header, pngChunk('IDAT', deflateSync(new Uint8Array((width * 4 + 1) * height))), pngChunk('IEND'));
}
function jpegSegment(marker: number, payload: Uint8Array) {
  const length = payload.length + 2;
  return join(Uint8Array.of(255, marker, length >>> 8, length), payload);
}
function jpegOffset(marker: number) {
  for (let p = 2; p < JPEG.length;) {
    if (JPEG[p + 1] === marker) return p;
    p += 2 + JPEG[p + 2] * 256 + JPEG[p + 3];
  }
  throw new Error('Missing fixture marker');
}
const withJpegBefore = (marker: number, chunk: Uint8Array) => {
  const offset = jpegOffset(marker);
  return join(JPEG.slice(0, offset), chunk, JPEG.slice(offset));
};
function riffChunk(kind: string, data: Uint8Array) {
  return join(ascii(kind), le32(data.length), data, data.length % 2 ? Uint8Array.of(0) : new Uint8Array());
}
function webp(...chunks: Uint8Array[]) {
  const body = join(ascii('WEBP'), ...chunks);
  return join(ascii('RIFF'), le32(body.length), body);
}
function vp8x(width = 3, height = 2, flags = 0) {
  return riffChunk('VP8X', join(Uint8Array.of(flags, 0, 0, 0), le32(width - 1).slice(0, 3), le32(height - 1).slice(0, 3)));
}

describe('approved storyboard raster static admission', () => {
  it.each(fixtures)('inspects the real %s fixture without mutating any bytes', (_name, bytes, mime) => {
    const before = bytes.slice();
    expect(inspectStoryboardRaster(bytes, mime)).toEqual({ width: 3, height: 2 });
    expect(bytes).toEqual(before);
  });

  it('accepts small/non-mask-aligned dimensions and inclusive side/pixel bounds', () => {
    for (const [width, height] of [[1, 1], [7, 3], [4096, 1024], [2048, 2048]]) {
      expect(inspectStoryboardRaster(validPng(width, height), 'image/png')).toEqual({ width, height });
    }
  });

  it.each([[0, 1], [1, 0], [4097, 1], [1, 4097], [2049, 2048], [4096, 4096], [0xffffffff, 1]])('rejects PNG dimensions %ix%i before decoding', (width, height) => {
    expect(() => inspectStoryboardRaster(pngWithHeader(width, height), 'image/png')).toThrow('Image dimensions exceed');
  });

  it('rejects input over 8 MiB and unsupported or mismatched MIME declarations', () => {
    expect(() => inspectStoryboardRaster(new Uint8Array(8 * 1024 * 1024 + 1), 'image/png')).toThrow('8 MiB');
    for (const mime of ['image/svg+xml', 'image/gif', 'image/avif', 'image/jpg', 'image/png; charset=utf-8', '']) {
      expect(() => inspectStoryboardRaster(PNG, mime)).toThrow('only static PNG, JPEG, and WebP');
    }
    expect(() => inspectStoryboardRaster(PNG, 'image/jpeg')).toThrow('JPEG');
    expect(() => inspectStoryboardRaster(JPEG, 'image/webp')).toThrow('WebP');
    expect(() => inspectStoryboardRaster(WEBP_LOSSY, 'image/png')).toThrow('PNG');
  });

  it.each(fixtures)('rejects every truncated prefix and trailing junk of %s', (_name, bytes, mime) => {
    for (let end = 0; end < bytes.length; end++) expect(() => inspectStoryboardRaster(bytes.slice(0, end), mime)).toThrow();
    expect(() => inspectStoryboardRaster(join(bytes, Uint8Array.of(0)), mime)).toThrow();
  });
});

describe('PNG closed profile and container validation', () => {
  it.each(['acTL', 'fcTL', 'fdAT', 'iCCP', 'zTXt', 'iTXt', 'tEXt', 'eXIf', 'zzZZ'])('rejects %s intact before native decode', kind => {
    const bytes = pngAfterHeader(pngChunk(kind, ascii('private-profile-content'))), before = bytes.slice();
    expect(() => inspectStoryboardRaster(bytes, 'image/png')).toThrow('PNG metadata or animation is not supported');
    expect(bytes).toEqual(before);
    try { inspectStoryboardRaster(bytes, 'image/png'); } catch (error) {
      expect(String(error)).not.toContain('private-profile-content');
    }
  });

  it('preserves admitted bounded, uncompressed color metadata', () => {
    const chromaticity = join(...[31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000].map(be32));
    const color = join(pngChunk('gAMA', be32(45455)), pngChunk('sRGB', Uint8Array.of(0)), pngChunk('cHRM', chromaticity));
    const bytes = pngAfterHeader(color), before = bytes.slice();
    expect(inspectStoryboardRaster(bytes, 'image/png')).toEqual({ width: 3, height: 2 });
    expect(bytes).toEqual(before);
  });

  it('checks every CRC and chunk length, including ancillary chunks', () => {
    const corrupted = PNG.slice(); corrupted[50] ^= 1;
    expect(() => inspectStoryboardRaster(corrupted, 'image/png')).toThrow('PNG has an invalid');
    const corruptCrc = pngAfterHeader(pngChunk('sRGB', Uint8Array.of(0))); corruptCrc[45] ^= 1;
    expect(() => inspectStoryboardRaster(corruptCrc, 'image/png')).toThrow('PNG has an invalid');
    const oversize = PNG.slice(); oversize.set(be32(0xffffffff), 33);
    expect(() => inspectStoryboardRaster(oversize, 'image/png')).toThrow('PNG has an invalid');
  });

  it('rejects duplicate headers, missing pixels, nonconsecutive data and excessive chunks', () => {
    expect(() => inspectStoryboardRaster(pngAfterHeader(PNG.slice(8, 33)), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(join(PNG.slice(0, 33), pngChunk('IEND')), 'image/png')).toThrow();
    const interrupted = join(PNG.slice(0, -12), pngChunk('pHYs', new Uint8Array(9)), pngChunk('IDAT'), pngChunk('IEND'));
    expect(() => inspectStoryboardRaster(interrupted, 'image/png')).toThrow();
    const tooMany = join(PNG.slice(0, -12), ...Array.from({ length: 1024 }, () => pngChunk('IDAT')), pngChunk('IEND'));
    expect(() => inspectStoryboardRaster(tooMany, 'image/png')).toThrow();
  });

  it('accepts a zlib header split across consecutive IDAT chunks', () => {
    const data = PNG.slice(41, -16);
    const bytes = join(PNG.slice(0, 33), pngChunk('IDAT', data.slice(0, 1)), pngChunk('IDAT', data.slice(1)), pngChunk('IEND'));
    expect(inspectStoryboardRaster(bytes, 'image/png')).toEqual({ width: 3, height: 2 });
  });

  it('admits bounded palette transparency and rejects invalid palette records', () => {
    const header = pngWithHeader(3, 2, 3, 1).slice(0, 33);
    const palette = pngChunk('PLTE', Uint8Array.of(0, 0, 0, 255, 255, 255));
    const alpha = pngChunk('tRNS', Uint8Array.of(0, 255));
    const pixels = pngChunk('IDAT', deflateSync(Uint8Array.of(0, 0xa0, 0, 0x40)));
    expect(inspectStoryboardRaster(join(header, palette, alpha, pixels, pngChunk('IEND')), 'image/png')).toEqual({ width: 3, height: 2 });
    expect(() => inspectStoryboardRaster(join(header, alpha, palette, pixels, pngChunk('IEND')), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(join(header, pngChunk('PLTE', new Uint8Array(9)), pixels, pngChunk('IEND')), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(join(header, palette, pngChunk('tRNS', new Uint8Array(3)), pixels, pngChunk('IEND')), 'image/png')).toThrow();
  });

  it('rejects invalid zlib headers and forbidden PNG profile fields', () => {
    for (const data of [Uint8Array.of(0, 0, 0, 0, 0, 0), Uint8Array.of(0x78, 0x20, 0, 0, 0, 0)]) {
      expect(() => inspectStoryboardRaster(join(PNG.slice(0, 33), pngChunk('IDAT', data), pngChunk('IEND')), 'image/png')).toThrow();
    }
    expect(() => inspectStoryboardRaster(pngWithHeader(3, 2, 6, 4), 'image/png')).toThrow();
    const interlacedHeader = PNG.slice(16, 29); interlacedHeader[12] = 1;
    expect(() => inspectStoryboardRaster(join(PNG.slice(0, 8), pngChunk('IHDR', interlacedHeader), PNG.slice(33)), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(pngAfterHeader(pngChunk('sRGB', Uint8Array.of(4))), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(pngAfterHeader(pngChunk('gAMA', be32(0))), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(pngAfterHeader(pngChunk('tRNS', Uint8Array.of(0))), 'image/png')).toThrow();
    expect(() => inspectStoryboardRaster(pngWithHeader(3, 2, 3, 8), 'image/png')).toThrow();
  });
});

describe('JPEG baseline-only closed profile', () => {
  it.each([0xe1, 0xe2, 0xe3, 0xed, 0xee, 0xef, 0xfe])('rejects unsafe/unsupported metadata marker %i', marker => {
    expect(() => inspectStoryboardRaster(withJpegBefore(0xdb, jpegSegment(marker, ascii('ICC_PROFILE\0private-data'))), 'image/jpeg')).toThrow('JPEG metadata');
  });

  it('allows ordinary minimal JFIF or a baseline image without APP metadata', () => {
    expect(inspectStoryboardRaster(join(JPEG.slice(0, 2), JPEG.slice(20)), 'image/jpeg')).toEqual({ width: 3, height: 2 });
    const withThumbnail = JPEG.slice(); withThumbnail[18] = 1;
    expect(() => inspectStoryboardRaster(withThumbnail, 'image/jpeg')).toThrow('JPEG metadata');
    expect(() => inspectStoryboardRaster(withJpegBefore(0xdb, jpegSegment(0xe0, ascii('JFXX\0'))), 'image/jpeg')).toThrow('JPEG metadata');
  });

  it('rejects duplicate, progressive, zero-height and oversized frame dimensions', () => {
    const p = jpegOffset(0xc0), size = 2 + JPEG[p + 2] * 256 + JPEG[p + 3];
    expect(() => inspectStoryboardRaster(withJpegBefore(0xda, JPEG.slice(p, p + size)), 'image/jpeg')).toThrow();
    const progressive = JPEG.slice(); progressive[p + 1] = 0xc2;
    expect(() => inspectStoryboardRaster(progressive, 'image/jpeg')).toThrow();
    for (const [width, height] of [[3, 0], [4097, 1], [2049, 2048]]) {
      const image = JPEG.slice(); image.set(Uint8Array.of(height >>> 8, height, width >>> 8, width), p + 5);
      expect(() => inspectStoryboardRaster(image, 'image/jpeg')).toThrow('Image dimensions exceed');
    }
  });

  it('requires consistent quantization, Huffman, frame and single scan records', () => {
    const malformedLength = JPEG.slice(); malformedLength[2 + 2] = 0; malformedLength[2 + 3] = 1;
    expect(() => inspectStoryboardRaster(malformedLength, 'image/jpeg')).toThrow();
    const badQuant = JPEG.slice(); badQuant[jpegOffset(0xdb) + 5] = 0;
    expect(() => inspectStoryboardRaster(badQuant, 'image/jpeg')).toThrow();
    const badHuffman = JPEG.slice(); badHuffman[jpegOffset(0xc4) + 5] = 255;
    expect(() => inspectStoryboardRaster(badHuffman, 'image/jpeg')).toThrow();
    const wrongTable = JPEG.slice(); wrongTable[jpegOffset(0xda) + 6] = 0x33;
    expect(() => inspectStoryboardRaster(wrongTable, 'image/jpeg')).toThrow();
    const badScan = JPEG.slice(); badScan[jpegOffset(0xda) + 4] = 2;
    expect(() => inspectStoryboardRaster(badScan, 'image/jpeg')).toThrow();
    const dnl = jpegSegment(0xdc, Uint8Array.of(0, 2));
    expect(() => inspectStoryboardRaster(join(JPEG.slice(0, -2), dnl, JPEG.slice(-2)), 'image/jpeg')).toThrow();
    expect(() => inspectStoryboardRaster(join(JPEG.slice(0, -2), JPEG.slice(jpegOffset(0xda))), 'image/jpeg')).toThrow();
    expect(() => inspectStoryboardRaster(join(JPEG.slice(0, -2), Uint8Array.of(255, 0xd0), JPEG.slice(-2)), 'image/jpeg')).toThrow();
  });
});

describe('WebP static closed profile', () => {
  it('admits a matching extended canvas for lossy and lossless image data', () => {
    expect(inspectStoryboardRaster(webp(vp8x(), WEBP_LOSSY.slice(12)), 'image/webp')).toEqual({ width: 3, height: 2 });
    expect(inspectStoryboardRaster(webp(vp8x(3, 2, 0x10), WEBP_LOSSLESS.slice(12)), 'image/webp')).toEqual({ width: 3, height: 2 });
  });

  it.each(['ANIM', 'ANMF', 'ICCP', 'EXIF', 'XMP ', 'JUNK'])('rejects %s chunks rather than stripping them', kind => {
    expect(() => inspectStoryboardRaster(webp(vp8x(), riffChunk(kind, Uint8Array.of(0, 0)), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow('WebP metadata');
  });

  it.each([0x02, 0x04, 0x08, 0x20, 0x01, 0x40, 0x80])('rejects animation, metadata and reserved VP8X flag %i', flags => {
    expect(() => inspectStoryboardRaster(webp(vp8x(3, 2, flags), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow('WebP metadata');
  });

  it('requires exact RIFF size, chunk size, zero padding and a single image record', () => {
    const shortRiff = WEBP_LOSSY.slice(); shortRiff.set(le32(shortRiff.length - 9), 4);
    expect(() => inspectStoryboardRaster(shortRiff, 'image/webp')).toThrow();
    const longChunk = WEBP_LOSSY.slice(); longChunk.set(le32(0xffffffff), 16);
    expect(() => inspectStoryboardRaster(longChunk, 'image/webp')).toThrow();
    const nonzeroPad = WEBP_LOSSLESS.slice(); nonzeroPad[nonzeroPad.length - 1] = 1;
    expect(() => inspectStoryboardRaster(nonzeroPad, 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(WEBP_LOSSY.slice(12), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x(), vp8x(), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(WEBP_LOSSY.slice(12), vp8x()), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x()), 'image/webp')).toThrow();
  });

  it('rejects mismatched, oversized or ambiguously scaled dimensions', () => {
    expect(() => inspectStoryboardRaster(webp(vp8x(4, 2), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x(3, 3, 0x10), WEBP_LOSSLESS.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x(4097, 2), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow('Image dimensions exceed');
    const wideLossy = WEBP_LOSSY.slice(); wideLossy.set(Uint8Array.of(1, 16), 26);
    expect(() => inspectStoryboardRaster(wideLossy, 'image/webp')).toThrow('Image dimensions exceed');
    const wideLossless = WEBP_LOSSLESS.slice(); wideLossless.set(le32(4096 + (1 << 14)), 21);
    expect(() => inspectStoryboardRaster(wideLossless, 'image/webp')).toThrow('Image dimensions exceed');
    const scaled = WEBP_LOSSY.slice(); scaled[27] |= 0x40;
    expect(() => inspectStoryboardRaster(scaled, 'image/webp')).toThrow();
  });

  it('validates keyframe, partition, signature and lossless version fields', () => {
    for (const [offset, value] of [[20, WEBP_LOSSY[20] | 1], [23, 0], [20, WEBP_LOSSY[20] & ~0x10], [22, 0xff]]) {
      const image = WEBP_LOSSY.slice(); image[offset] = value;
      expect(() => inspectStoryboardRaster(image, 'image/webp')).toThrow();
    }
    const emptyPartition = WEBP_LOSSY.slice(); emptyPartition.set(Uint8Array.of(0x10, 0, 0), 20);
    expect(() => inspectStoryboardRaster(emptyPartition, 'image/webp')).toThrow();
    const badVersion = WEBP_LOSSLESS.slice(); badVersion[24] |= 0x20;
    expect(() => inspectStoryboardRaster(badVersion, 'image/webp')).toThrow();
    const badReserved = webp(vp8x(), WEBP_LOSSY.slice(12)); badReserved[21] = 1;
    expect(() => inspectStoryboardRaster(badReserved, 'image/webp')).toThrow();
  });

  it('validates alpha presence, size, compression and ordering', () => {
    expect(() => inspectStoryboardRaster(webp(vp8x(3, 2, 0x10), WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x(), WEBP_LOSSLESS.slice(12)), 'image/webp')).toThrow();
    const alphaChunk = WEBP_ALPHA.slice(30, 46);
    expect(() => inspectStoryboardRaster(webp(alphaChunk, WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    expect(() => inspectStoryboardRaster(webp(vp8x(3, 2, 0x10), alphaChunk, WEBP_LOSSLESS.slice(12)), 'image/webp')).toThrow();
    const shortAlpha = riffChunk('ALPH', Uint8Array.of(0, 128));
    expect(() => inspectStoryboardRaster(webp(vp8x(3, 2, 0x10), shortAlpha, WEBP_LOSSY.slice(12)), 'image/webp')).toThrow();
    for (const header of [2, 3, 0x20, 0x40]) {
      const image = WEBP_ALPHA.slice(); image[38] = header;
      expect(() => inspectStoryboardRaster(image, 'image/webp')).toThrow();
    }
  });

  it('admits a real static 17x9 WebP with compressed pixel alpha', () => {
    // ALPH is bounded pixel data whose dimensions come from the checked canvas;
    // unlike ICC/XMP/EXIF it is not an unbounded metadata expansion surface.
    const image = fromBase64('UklGRmQAAABXRUJQVlA4WAoAAAAQAAAAEAAACAAAQUxQSAoAAAABB1DAiAhERP8DVlA4IDQAAADQAgCdASoRAAkAPm0skkWkIqGYBABABsSxgDsAAIGwAP71uH//amCSMpf/+6DLOG6QAAAA');
    expect(inspectStoryboardRaster(image, 'image/webp')).toEqual({ width: 17, height: 9 });
  });
});
