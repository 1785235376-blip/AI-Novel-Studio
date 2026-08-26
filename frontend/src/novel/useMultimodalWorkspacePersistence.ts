import { useEffect, useState } from 'react';
import type { DirectorShot } from './MultimodalDirectorWorkspace';

type RefNode = { uri: string; x: number; y: number; role: string };
type Snapshot = { at: string; note?: string; refs: RefNode[]; shots: DirectorShot[] };

export function useMultimodalWorkspacePersistence(key: string, initialShots: DirectorShot[] = []) {
  const [refs, setRefs] = useState<RefNode[]>([]);
  const [shots, setShots] = useState<DirectorShot[]>(initialShots);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const snapshotKey = `${key}:snapshots`;
  useEffect(() => { try { const saved = JSON.parse(localStorage.getItem(key) || '{}'); if (Array.isArray(saved.refs)) setRefs(saved.refs); if (Array.isArray(saved.shots)) setShots(saved.shots); const history = JSON.parse(localStorage.getItem(snapshotKey) || '[]'); if (Array.isArray(history)) setSnapshots(history.slice(0, 5)); } catch { /* local storage is optional */ } }, [key, snapshotKey]);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify({ refs, shots })); } catch { /* storage may be disabled */ } }, [key, refs, shots]);
  const snapshot = (note = '') => { const next = [{ at: new Date().toISOString(), note, refs, shots }, ...snapshots].slice(0, 5); setSnapshots(next); try { localStorage.setItem(snapshotKey, JSON.stringify(next)); } catch { /* optional */ } };
  const restore = (item: Snapshot = snapshots[0]) => { if (item) { setRefs(item.refs); setShots(item.shots); } };
  const importWorkspace = (value: unknown) => { if (!value || typeof value !== 'object') return false; const data = value as { references?: RefNode[]; shots?: DirectorShot[] }; if (!Array.isArray(data.references) && !Array.isArray(data.shots)) return false; if (Array.isArray(data.references)) setRefs(data.references.filter(item => item && typeof item.uri === 'string')); if (Array.isArray(data.shots)) setShots(data.shots.filter(item => item && typeof item.name === 'string')); return true; };
  const clear = (note = '') => { snapshot(note); setRefs([]); setShots(initialShots); try { localStorage.removeItem(key); } catch { /* optional */ } };
  return { refs, setRefs, shots, setShots, snapshots, snapshot, restore, clear, importWorkspace };
}
