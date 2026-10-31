import { describe, expect, it } from 'vitest';
import { checkedCanvasAudioTaskEnvelope } from './canvasAudioTaskEnvelope';

const range = { in_ms: 200, out_ms: 1200 };

describe('closed canvas AudioJob envelope parameters', () => {
  it('preserves omission, explicit zero and finite fractional gain without mutating input', () => {
    expect(checkedCanvasAudioTaskEnvelope(range)).toEqual(range);
    const value = Object.freeze({ ...range, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0 });
    expect(checkedCanvasAudioTaskEnvelope(value)).toEqual(value);
    expect(checkedCanvasAudioTaskEnvelope(value)).not.toBe(value);
    expect(checkedCanvasAudioTaskEnvelope({ ...range, gain_db: -6.020599913279624, fade_in_ms: 200, fade_out_ms: 300 }))
      .toEqual({ ...range, gain_db: -6.020599913279624, fade_in_ms: 200, fade_out_ms: 300 });
  });

  it.each([-60, 12])('accepts original gain boundary %s', gain_db => {
    expect(checkedCanvasAudioTaskEnvelope({ ...range, gain_db })?.gain_db).toBe(gain_db);
  });
  it('accepts exact source and duration boundaries and touching fades', () => {
    const value = { in_ms: 480000, out_ms: 600000, fade_in_ms: 60000, fade_out_ms: 60000 };
    expect(checkedCanvasAudioTaskEnvelope(value)).toEqual(value);
    expect(checkedCanvasAudioTaskEnvelope({ in_ms: 0, out_ms: 120000, fade_in_ms: 120000 }))
      .toEqual({ in_ms: 0, out_ms: 120000, fade_in_ms: 120000 });
  });
  it.each([null, undefined, true, 1, 'parameters', [], {}, { in_ms: 0 }, { out_ms: 1 },
    Object.create(range)])('rejects missing or non-own source bounds %#', value => {
    expect(checkedCanvasAudioTaskEnvelope(value)).toBeUndefined();
  });
  it.each(['in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms'] as const)(
    'rejects coercible or null control values for %s in fresh and recorded commands', key => {
      for (const value of [null, undefined, true, false, '0', Number.NaN, Infinity, -Infinity]) {
        const parameters = { ...range, [key]: value };
        expect(checkedCanvasAudioTaskEnvelope(parameters)).toBeUndefined();
        expect(checkedCanvasAudioTaskEnvelope(parameters, true)).toBeUndefined();
      }
    });
  it.each([
    { in_ms: -1 }, { out_ms: -1 }, { in_ms: 0.5 }, { out_ms: 1200.5 },
    { in_ms: 600001, out_ms: 600002 }, { out_ms: 600001 }, { out_ms: 200 }, { out_ms: 199 },
    { in_ms: 0, out_ms: 120001 }, { gain_db: -60.1 }, { gain_db: 12.1 },
    { fade_in_ms: -1 }, { fade_out_ms: -1 }, { fade_in_ms: 0.5 }, { fade_out_ms: 0.5 },
    { fade_in_ms: 120001 }, { fade_out_ms: 120001 }, { fade_in_ms: 1001 },
    { fade_in_ms: 501, fade_out_ms: 500 },
  ])('rejects out-of-bound envelope %#', change => {
    expect(checkedCanvasAudioTaskEnvelope({ ...range, ...change })).toBeUndefined();
  });
  it('permits only the original recorded null projection, never new control nulls or values', () => {
    const projection = Object.fromEntries(['width', 'height', 'steps', 'seed', 'cfg', 'negative_prompt',
      'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate'].map(key => [key, null]));
    const value = { ...range, gain_db: -6, fade_in_ms: 100, ...projection };
    expect(checkedCanvasAudioTaskEnvelope(value)).toBeUndefined();
    expect(checkedCanvasAudioTaskEnvelope(value, true)).toEqual({ ...range, gain_db: -6, fade_in_ms: 100 });
    for (const key of Object.keys(projection)) {
      expect(checkedCanvasAudioTaskEnvelope({ ...range, [key]: 0 }, true)).toBeUndefined();
      expect(checkedCanvasAudioTaskEnvelope({ ...range, [key]: undefined }, true)).toBeUndefined();
    }
  });
  it.each(['sample_rate', 'channels', 'output_format', 'target_lufs', 'target_peak_dbfs', 'denoise_profile',
    'normalize', 'codec', 'unknown_control'])('refuses control expansion even for recorded %s:null', key => {
    for (const value of [null, 0, 'WAV']) {
      expect(checkedCanvasAudioTaskEnvelope({ ...range, [key]: value })).toBeUndefined();
      expect(checkedCanvasAudioTaskEnvelope({ ...range, [key]: value }, true)).toBeUndefined();
    }
  });
  it('does not ignore symbol or nonenumerable extra controls', () => {
    expect(checkedCanvasAudioTaskEnvelope({ ...range, [Symbol('control')]: true })).toBeUndefined();
    expect(checkedCanvasAudioTaskEnvelope(Object.defineProperty({ ...range }, 'output_format', { value: 'FLAC' })))
      .toBeUndefined();
  });
});
