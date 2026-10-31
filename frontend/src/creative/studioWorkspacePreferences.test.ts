import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import { checkedStudioPreferences, preferenceSaveFailure, samePreferenceInput } from './studioWorkspacePreferences';

// Deferred by the user. These cases record source-level regressions to execute later.
describe('studio workspace preference boundaries', () => {
  const input = { intents: ['IMAGE_DESIGN', 'CUSTOM'] as const, preset: 'IMAGE' as const, custom_intent: '中文创作' };
  it('treats intent ordering as the same presentation hint', () => {
    expect(samePreferenceInput({ ...input, intents: [...input.intents] }, { ...input, intents: ['CUSTOM', 'IMAGE_DESIGN'] })).toBe(true);
    expect(samePreferenceInput({ ...input, intents: [...input.intents] }, { ...input, intents: ['CUSTOM'] })).toBe(false);
  });
  it.each([
    { version: true }, { version: -1 }, { version: 0.5 }, { version: '1' },
    { intents: ['IMAGE_DESIGN', 'IMAGE_DESIGN'] }, { intents: ['UNKNOWN'] }, { intents: null },
    { preset: 'FULL_ACCESS' }, { custom_intent: 'x'.repeat(241) },
  ])('rejects malformed successful preference DTOs without coercion: %j', changes => {
    expect(() => checkedStudioPreferences({ ...input, version: 1, ...changes })).toThrow(ApiError);
  });
  it('projects the original allowed fields and keeps private extensions out', () => {
    const result = checkedStudioPreferences({ ...input, version: 0, session_token: 'private', rights_granted: true });
    expect(result).toEqual({ ...input, version: 0 });
    expect(result).not.toHaveProperty('session_token');
    expect(result).not.toHaveProperty('rights_granted');
  });
  it('keeps mutation uncertainty distinct from a rejected CAS or validation request', () => {
    const error = (status: number, code = 'STUDIO_REQUEST_FAILED') => new ApiError({ status, code, message: 'synthetic' });
    expect(preferenceSaveFailure(error(409))).toBe('CONFLICT');
    expect(preferenceSaveFailure(error(422))).toBe('REJECTED');
    expect(preferenceSaveFailure(error(401))).toBe('REJECTED');
    expect(preferenceSaveFailure(error(0))).toBe('UNKNOWN');
    expect(preferenceSaveFailure(error(503))).toBe('UNKNOWN');
    expect(preferenceSaveFailure(error(200, 'STUDIO_RESPONSE_INVALID'))).toBe('UNKNOWN');
    expect(preferenceSaveFailure(new DOMException('synthetic', 'AbortError'))).toBe('UNKNOWN');
  });
});
