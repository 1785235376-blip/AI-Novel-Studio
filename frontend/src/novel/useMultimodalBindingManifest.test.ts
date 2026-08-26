// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useMultimodalBindingManifest } from './useMultimodalBindingManifest';

describe('useMultimodalBindingManifest', () => {
  it('deduplicates and removes bound entities', () => {
    localStorage.clear();
    const { result } = renderHook(() => useMultimodalBindingManifest('bindings'));
    act(() => { result.current.add('characters', '主角'); result.current.add('characters', '主角'); result.current.add('props', '怀表'); });
    expect(result.current.manifest.characters).toEqual(['主角']);
    act(() => result.current.remove('props', '怀表'));
    expect(result.current.manifest.props).toEqual([]);
  });
  it('keeps separate character, scene, and prop indexes', () => {
    localStorage.clear();
    const { result } = renderHook(() => useMultimodalBindingManifest('binding-index'));
    act(() => { result.current.add('characters', '主角'); result.current.add('scenes', '车站'); result.current.add('props', '怀表 · prop-1'); });
    expect(result.current.manifest).toMatchObject({ characters: ['主角'], scenes: ['车站'], props: ['怀表 · prop-1'] });
  });
});
