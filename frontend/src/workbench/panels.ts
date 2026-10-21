/**
 * [HERMIA-FE-20261022 slice M1-1] Typed panel registry (task book §7.1).
 * Declares stable id, kind, title, capability status, size constraints, instancing
 * rule and dock zones. Existing FEATURE_GROUPS ids are bridged 1:1 (see featureBridge.ts)
 * so old entry → new entry mapping is lossless; no existing panel is removed.
 */
export type DockZone = 'left' | 'main' | 'right' | 'bottom';
/** Implementation status column (§5) — never mixed with verification evidence. */
export type CapabilityStatus = 'connected' | 'partial' | 'local-only' | 'not-implemented' | 'undetermined';
export interface PanelDefinition {
  id: string; kind: 'feature' | 'editor' | 'canvas' | 'inspector' | 'demo';
  title: string; group?: string;
  capability: CapabilityStatus;
  /** 'singleton' = one instance; 'per-object' = keyed by stable object ref (never by name/index). */
  instancing: 'singleton' | 'per-object';
  docks: readonly DockZone[]; defaultDock: DockZone;
  minWidth?: number; requiresContext?: readonly ('project' | 'document' | 'node')[];
  devOnly?: boolean;
  /** Hooks for lifecycle; onDispose must release subscriptions/media handles. */
  onDispose?: (instanceKey: string) => void;
}
export class PanelRegistry {
  private defs = new Map<string, PanelDefinition>();
  constructor(private isDev = false) {}
  register(def: PanelDefinition): () => void {
    if (this.defs.has(def.id)) throw new Error(`duplicate panel id: ${def.id}`);
    if (!def.docks.includes(def.defaultDock)) throw new Error(`panel ${def.id}: defaultDock not in docks`);
    this.defs.set(def.id, def); return () => { this.defs.delete(def.id); };
  }
  get(id: string) { const d = this.defs.get(id); return d && (!d.devOnly || this.isDev) ? d : undefined; }
  has(id: string) { return !!this.get(id); }
  list(): PanelDefinition[] { return [...this.defs.values()].filter(d => !d.devOnly || this.isDev); }
  instanceKey(id: string, objectRef?: string | null): string {
    const d = this.get(id); if (!d) throw new Error(`unknown panel ${id}`);
    if (d.instancing === 'singleton') return id;
    if (!objectRef) throw new Error(`panel ${id} requires a stable object ref`);
    return `${id}#${objectRef}`;
  }
}
