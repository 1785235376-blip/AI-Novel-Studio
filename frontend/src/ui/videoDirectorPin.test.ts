// @vitest-environment jsdom
/**
 * [HERMIA-FE-20261022 W-UX-15] session pin helper for VIDEO director layer.
 */
import {afterEach, describe, expect, it} from 'vitest';
import {
  clearVideoDirectorPins,
  readVideoDirectorPin,
  resolveVideoDirectorOpen,
  writeVideoDirectorPin,
} from './videoDirectorPin';

afterEach(() => clearVideoDirectorPins());

describe('videoDirectorPin W-UX-15', () => {
  it('defaults to shellMode when unset', () => {
    expect(resolveVideoDirectorOpen('n1', 'basic')).toEqual({open: false, source: 'shellMode'});
    expect(resolveVideoDirectorOpen('n1', 'pro')).toEqual({open: true, source: 'shellMode'});
    expect(readVideoDirectorPin('n1')).toBeNull();
  });

  it('user toggle wins across reads (module-hop)', () => {
    writeVideoDirectorPin('n1', true);
    expect(resolveVideoDirectorOpen('n1', 'basic')).toEqual({open: true, source: 'session'});
    writeVideoDirectorPin('n1', false);
    expect(resolveVideoDirectorOpen('n1', 'pro')).toEqual({open: false, source: 'session'});
    expect(readVideoDirectorPin('n1')).toEqual({open: false, userSet: true});
  });

  it('scopes pins per novelId', () => {
    writeVideoDirectorPin('a', true);
    writeVideoDirectorPin('b', false);
    expect(resolveVideoDirectorOpen('a', 'basic').open).toBe(true);
    expect(resolveVideoDirectorOpen('b', 'pro').open).toBe(false);
  });
});
