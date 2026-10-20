import { describe, expect, it } from 'vitest';
import { formatAudioTrimTimecode, parseAudioTrimTimecode } from './studioAudioTrimTimecode';

describe('audio trim timecodes', () => {
  it.each([
    ['0:00', 0], ['1:23.450', 83450], ['00:01:23.45', 83450],
    ['0:00.001', 1], ['0:00.1', 100], [' 10:00.000 ', 600000], ['00:10:00', 600000],
  ] as const)('converts %s to exact integer milliseconds', (value, expected) => {
    expect(parseAudioTrimTimecode(value)).toBe(expected);
  });
  it.each(['', '1000', '-1:00', '0:60', '00:60:00', '1:2', '0:00.', '0:00.0001', '10:00.001', '01:00:00', '1e1:00', '0:00x'])('rejects ambiguous, malformed or out-of-contract %s', value => {
    expect(parseAudioTrimTimecode(value)).toBeNull();
  });
  it.each(['0', '1', '100', '83450', '600000'])('round trips the original millisecond value %s', value => {
    expect(parseAudioTrimTimecode(formatAudioTrimTimecode(value))).toBe(Number(value));
  });
  it.each(['', '-1', '1.5', 'NaN', '600001'])('does not guess an invalid draft position %s', value => {
    expect(formatAudioTrimTimecode(value)).toBe('');
  });
});
