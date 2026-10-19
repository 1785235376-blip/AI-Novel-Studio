import { describe, expect, it } from 'vitest';
import type { Asset } from '../api';
import { assetLibraryView } from './assetLibraryView';

const asset = (id: string, filename: string, size: number, created_at: string): Asset => ({
  id, filename, size, created_at, novel_id: 'n1', kind: 'file', media_type: 'text/plain',
  sha256: 'a'.repeat(64), updated_at: created_at,
});

describe('original asset library view', () => {
  const rows = [asset('a', 'Scene10.TXT', 4, ''), asset('b', 'scene2.txt', 20, '2026-10-18T12:00:00Z'),
    asset('c', 'notes.md', 20, '2026-10-19T12:00:00Z'), asset('d', 'unknown.md', 2, 'invalid')];

  it('searches only filenames already returned by the owner', () => {
    expect(assetLibraryView(rows, ' SCENE ', 'OWNER')).toEqual(rows.slice(0, 2));
    expect(assetLibraryView(rows, 'text/plain', 'OWNER')).toEqual([]);
    expect(assetLibraryView(rows, 'n1', 'OWNER')).toEqual([]);
  });

  it('sorts naturally by name, newest date or size, without mutating owner order or objects', () => {
    const frozen = Object.freeze(rows.map(row => Object.freeze({ ...row })));
    expect(assetLibraryView(frozen, 'scene', 'NAME').map(row => row.id)).toEqual(['b', 'a']);
    expect(assetLibraryView(frozen, '', 'NEWEST').map(row => row.id)).toEqual(['c', 'b', 'a', 'd']);
    expect(assetLibraryView(frozen, '', 'SIZE').map(row => row.id)).toEqual(['b', 'c', 'a', 'd']);
    const original = assetLibraryView(frozen, '', 'OWNER');
    expect(original.map(row => row.id)).toEqual(['a', 'b', 'c', 'd']);
    expect(original[0]).toBe(frozen[0]);
  });
});
