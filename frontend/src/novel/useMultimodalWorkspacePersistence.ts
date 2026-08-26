import { useCallback, useEffect, useRef, useState } from "react";
import type { DirectorShot } from "./MultimodalDirectorWorkspace";

export type CanvasViewport = { x: number; y: number; zoom: number };
export type RefNode = {
  id: string;
  uri: string;
  x: number;
  y: number;
  role: string;
  z: number;
  locked?: boolean;
  hidden?: boolean;
  groupId?: string;
};
type LegacyRefNode = Omit<RefNode, "id" | "z"> & { id?: string; z?: number };
type Snapshot = {
  at: string;
  note?: string;
  refs: RefNode[];
  shots: DirectorShot[];
  viewport?: CanvasViewport;
};
let idSequence = 0;
export const createCanvasNodeId = () =>
  `ref-${Date.now().toString(36)}-${(++idSequence).toString(36)}`;
const normalizeRefs = (items: LegacyRefNode[]) =>
  items.map((item, index) => ({
    ...item,
    id: item.id || createCanvasNodeId(),
    z: Number.isFinite(item.z) ? Number(item.z) : index,
  }));

export function useMultimodalWorkspacePersistence(
  key: string,
  initialShots: DirectorShot[] = [],
) {
  const [refs, setRefsState] = useState<RefNode[]>([]);
  const refsRef = useRef<RefNode[]>([]);
  const [shots, setShots] = useState<DirectorShot[]>(initialShots);
  const [viewport, setViewport] = useState<CanvasViewport>({
    x: 0,
    y: 0,
    zoom: 1,
  });
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [past, setPast] = useState<RefNode[][]>([]);
  const [future, setFuture] = useState<RefNode[][]>([]);
  const pastRef = useRef<RefNode[][]>([]);
  const futureRef = useRef<RefNode[][]>([]);
  const snapshotKey = `${key}:snapshots`;
  const assignRefs = useCallback((next: RefNode[]) => {
    refsRef.current = next;
    setRefsState(next);
  }, []);
  const setRefs = useCallback(
    (value: React.SetStateAction<RefNode[]>, record = true) => {
      const current = refsRef.current;
      const next = typeof value === "function" ? value(current) : value;
      if (JSON.stringify(current) === JSON.stringify(next)) return;
      if (record) {
        pastRef.current = [...pastRef.current.slice(-49), current];
        futureRef.current = [];
        setPast(pastRef.current);
        setFuture(futureRef.current);
      }
      assignRefs(next);
    },
    [assignRefs],
  );
  const undo = useCallback(() => {
    const previous = pastRef.current.at(-1);
    if (!previous) return;
    futureRef.current = [refsRef.current, ...futureRef.current].slice(0, 50);
    pastRef.current = pastRef.current.slice(0, -1);
    setPast(pastRef.current);
    setFuture(futureRef.current);
    assignRefs(previous);
  }, [assignRefs]);
  const redo = useCallback(() => {
    const next = futureRef.current[0];
    if (!next) return;
    pastRef.current = [...pastRef.current.slice(-49), refsRef.current];
    futureRef.current = futureRef.current.slice(1);
    setPast(pastRef.current);
    setFuture(futureRef.current);
    assignRefs(next);
  }, [assignRefs]);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "{}");
      assignRefs(Array.isArray(saved.refs) ? normalizeRefs(saved.refs) : []);
      if (Array.isArray(saved.shots)) setShots(saved.shots);
      if (saved.viewport && Number.isFinite(saved.viewport.zoom))
        setViewport(saved.viewport);
      const history = JSON.parse(localStorage.getItem(snapshotKey) || "[]");
      if (Array.isArray(history))
        setSnapshots(
          history
            .slice(0, 5)
            .map((item) => ({ ...item, refs: normalizeRefs(item.refs || []) })),
        );
      pastRef.current = [];
      futureRef.current = [];
      setPast([]);
      setFuture([]);
    } catch {
      assignRefs([]);
    }
  }, [assignRefs, key, snapshotKey]);
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify({ refs, shots, viewport }));
    } catch {
      /* storage may be disabled */
    }
  }, [key, refs, shots, viewport]);
  const snapshot = (note = "") => {
    const next = [
      { at: new Date().toISOString(), note, refs, shots, viewport },
      ...snapshots,
    ].slice(0, 5);
    setSnapshots(next);
    try {
      localStorage.setItem(snapshotKey, JSON.stringify(next));
    } catch {
      /* optional */
    }
  };
  const restore = (item: Snapshot = snapshots[0]) => {
    if (item) {
      setRefs(item.refs);
      setShots(item.shots);
      if (item.viewport) setViewport(item.viewport);
    }
  };
  const importWorkspace = (value: unknown) => {
    if (!value || typeof value !== "object") return false;
    const data = value as {
      references?: LegacyRefNode[];
      shots?: DirectorShot[];
    };
    if (!Array.isArray(data.references) && !Array.isArray(data.shots))
      return false;
    if (Array.isArray(data.references))
      setRefs(
        normalizeRefs(
          data.references.filter(
            (item) => item && typeof item.uri === "string",
          ),
        ),
      );
    if (Array.isArray(data.shots))
      setShots(
        data.shots.filter((item) => item && typeof item.name === "string"),
      );
    return true;
  };
  const clear = (note = "") => {
    snapshot(note);
    setRefs([]);
    setShots(initialShots);
    setViewport({ x: 0, y: 0, zoom: 1 });
    try {
      localStorage.removeItem(key);
    } catch {
      /* optional */
    }
  };
  return {
    refs,
    setRefs,
    shots,
    setShots,
    viewport,
    setViewport,
    snapshots,
    snapshot,
    restore,
    clear,
    importWorkspace,
    undo,
    redo,
    canUndo: past.length > 0,
    canRedo: future.length > 0,
  };
}
