import {describe, expect, it, vi} from 'vitest';
import {checkedCanvasVideoAudioOption} from './canvasVideoAudio';

describe('optional original video audio parameter', () => {
  it('leaves the legacy omitted wire untouched', () => {
    const parameters = Object.freeze({in_ms: 1000, out_ms: 1600});
    expect(checkedCanvasVideoAudioOption(parameters)).toBeUndefined();
    expect(Object.keys(parameters)).toEqual(['in_ms', 'out_ms']);
    expect(JSON.stringify(parameters)).toBe('{"in_ms":1000,"out_ms":1600}');
  });
  it.each([false, true])('retains an explicit %s', value => {
    expect(checkedCanvasVideoAudioOption(Object.freeze({include_audio: value}))).toBe(value);
  });
  it('reads only the own audio field without parsing unrelated parameters or inherited audio', () => {
    const inherited = Object.create({include_audio: true});
    inherited.in_ms = 'not this helper’s responsibility';
    expect(checkedCanvasVideoAudioOption(inherited)).toBeUndefined();
    expect(checkedCanvasVideoAudioOption({include_audio: false, unknown: null})).toBe(false);
    expect(checkedCanvasVideoAudioOption(Object.create(null))).toBeUndefined();
  });
  it.each([undefined, null, 'true', 'false', '', 0, 1, NaN, [], {}, new Boolean(true)])(
    'rejects a present nonboolean %s', value => {
      expect(() => checkedCanvasVideoAudioOption({include_audio: value})).toThrow('STUDIO_CANVAS_VIDEO_AUDIO_OPTION_INVALID');
    });
  it.each([undefined, null, false, 1, 'parameters', [], () => true])('rejects non-object parameters %s', value => {
    expect(() => checkedCanvasVideoAudioOption(value)).toThrow('STUDIO_CANVAS_VIDEO_AUDIO_OPTION_INVALID');
  });
  it('rejects accessors without invoking user code or inferring a default', () => {
    const getter = vi.fn(() => true);
    const parameters = Object.defineProperty({}, 'include_audio', {get: getter});
    expect(() => checkedCanvasVideoAudioOption(parameters)).toThrow();
    expect(getter).not.toHaveBeenCalled();
  });
});
