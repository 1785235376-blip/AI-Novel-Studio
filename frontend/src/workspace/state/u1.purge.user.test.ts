// [HERMIA-FE-20261025 M10-purgeguard] kills Vera mutations P6 (no identity ⇒ 'anonymous') and P7 (placeholder actor accepted). mock.
import {expect, it} from 'vitest';
import {resolveWorkspaceUser} from './scopeLease';
it('purge user: blank/absent actor ⇒ null (never an implicit anonymous user)', () => {
  for (const a of [undefined, null, '', '   ']) expect(resolveWorkspaceUser(a)).toBeNull();
});
it('purge user: placeholder actors are not users', () => {
  for (const a of ['local', 'local-author', 'preview', 'unknown', 'anonymous', 'default', ' Local-Author ']) expect(resolveWorkspaceUser(a)).toBeNull();
});
it('purge user: a real actor id is returned unchanged', () => { expect(resolveWorkspaceUser('actor-1')).toBe('actor-1'); });
