import { useEffect, useState } from 'react';

export type BindingManifest = { characters: string[]; scenes: string[]; props: string[]; updatedAt: string };

export function useMultimodalBindingManifest(key: string) {
  const [manifest, setManifest] = useState<BindingManifest>({ characters: [], scenes: [], props: [], updatedAt: '' });
  useEffect(() => { try { const value = JSON.parse(localStorage.getItem(key) || 'null'); if (value && typeof value === 'object') setManifest({ characters: Array.isArray(value.characters) ? value.characters : [], scenes: Array.isArray(value.scenes) ? value.scenes : [], props: Array.isArray(value.props) ? value.props : [], updatedAt: value.updatedAt || '' }); } catch { /* optional local index */ } }, [key]);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(manifest)); } catch { /* storage may be disabled */ } }, [key, manifest]);
  const add = (kind: 'characters' | 'scenes' | 'props', value: string) => { const item = value.trim(); if (!item) return; setManifest(current => ({ ...current, [kind]: Array.from(new Set([...current[kind], item])), updatedAt: new Date().toISOString() })); };
  const remove = (kind: 'characters' | 'scenes' | 'props', value: string) => setManifest(current => ({ ...current, [kind]: current[kind].filter(item => item !== value), updatedAt: new Date().toISOString() }));
  return { manifest, add, remove };
}
