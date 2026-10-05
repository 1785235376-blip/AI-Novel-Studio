export type LocalDraft = {
  chapterId: string;
  content: string;
  document?: unknown;
  baseVersion: number;
  updatedAt: string;
};

export type PersistentConflict = {
  chapterId: string;
  local: LocalDraft;
  server: { content: string; document?: unknown; version: number; [key: string]: unknown };
  detectedAt: string;
};

export type ConflictResolutionDraft = {
  chapterId: string;
  content: string;
  serverVersion: number;
  sourceConflictDetectedAt: string;
  updatedAt: string;
};

export type DraftDurability = 'durable' | 'memory' | 'none';
export type PersistenceReceipt = { durability: Exclude<DraftDurability, 'none'> };

// BACKPORT CANDIDATE (U02): a failed browser write must never interrupt editing
// or let an older durable snapshot replace the current, memory-only candidate.
// This overlay is deliberately volatile. A restart cannot recover its contents.
const volatile = new Map<string, string | null>();
const storage = {
  getItem(key: string): string | null {
    if (volatile.has(key)) return volatile.get(key) ?? null;
    try { return globalThis.localStorage?.getItem(key) ?? null; } catch { return null; }
  },
  setItem(key: string, value: string): PersistenceReceipt {
    volatile.set(key, value);
    try {
      if (!globalThis.localStorage) return { durability: 'memory' };
      globalThis.localStorage.setItem(key, value);
      // Some hosts silently reject writes. Only report the value read back.
      if (globalThis.localStorage.getItem(key) !== value) return { durability: 'memory' };
      volatile.delete(key);
      return { durability: 'durable' };
    } catch { return { durability: 'memory' }; }
  },
  removeItem(key: string) {
    // Keep a tombstone if storage rejects deletion, rather than resurrecting an
    // explicitly discarded/acknowledged candidate during this session.
    volatile.set(key, null);
    try {
      if (!globalThis.localStorage) return;
      globalThis.localStorage.removeItem(key);
      if (globalThis.localStorage.getItem(key) === null) volatile.delete(key);
    } catch { /* The tombstone remains memory-only; durable recovery may recur. */ }
  },
  durability(key: string): DraftDurability {
    if (volatile.has(key)) return volatile.get(key) === null ? 'none' : 'memory';
    return this.getItem(key) === null ? 'none' : 'durable';
  },
};

const scopedKey = (kind: string, id: string, namespace = 'file') =>
  `ai-novel-studio:${kind}:${namespace}:${id}`;

function loadJson<T>(key: string): T | undefined {
  try {
    const value = storage.getItem(key);
    return value ? (JSON.parse(value) as T) : undefined;
  } catch { return undefined; }
}

export const drafts = {
  load(id: string, namespace = 'file') {
    const value = loadJson<LocalDraft>(scopedKey('draft', id, namespace));
    return value?.chapterId === id && typeof value.content === 'string'
      && Number.isInteger(value.baseVersion) && value.baseVersion >= 0 ? value : undefined;
  },
  // One atomic versioned snapshot per chapter/scope is the local draft journal.
  // Existing records remain readable; no migration or server write is implied.
  save: (value: LocalDraft, namespace = 'file') =>
    storage.setItem(scopedKey('draft', value.chapterId, namespace), JSON.stringify(value)),
  durability: (id: string, namespace = 'file') => storage.durability(scopedKey('draft', id, namespace)),
  remove: (id: string, namespace = 'file') => storage.removeItem(scopedKey('draft', id, namespace)),
};

const sameConflict = (left: PersistentConflict, right: PersistentConflict) =>
  left.detectedAt === right.detectedAt &&
  left.local.updatedAt === right.local.updatedAt &&
  left.server.version === right.server.version;

export const conflicts = {
  load: (id: string, namespace = 'file') => loadJson<PersistentConflict>(scopedKey('conflict', id, namespace)),
  list: (id: string, namespace = 'file') => loadJson<PersistentConflict[]>(scopedKey('conflict-history', id, namespace)) ?? [],
  durability: (id: string, namespace = 'file') => storage.durability(scopedKey('conflict', id, namespace)),
  save(value: PersistentConflict, namespace = 'file') {
    const current = this.load(value.chapterId, namespace);
    const history = this.list(value.chapterId, namespace);
    if (current && !sameConflict(current, value) && !history.some(item => sameConflict(item, current))) {
      history.push(current);
      storage.setItem(scopedKey('conflict-history', value.chapterId, namespace), JSON.stringify(history));
    }
    return storage.setItem(scopedKey('conflict', value.chapterId, namespace), JSON.stringify(value));
  },
  resolve(id: string, namespace = 'file') {
    const current = this.load(id, namespace);
    const history = this.list(id, namespace);
    if (current && !history.some(item => sameConflict(item, current))) {
      storage.setItem(scopedKey('conflict-history', id, namespace), JSON.stringify([...history, current]));
    }
    return storage.removeItem(scopedKey('conflict', id, namespace));
  },
  remove: (id: string, namespace = 'file') => storage.removeItem(scopedKey('conflict', id, namespace)),
  clearHistory: (id: string, namespace = 'file') => storage.removeItem(scopedKey('conflict-history', id, namespace)),
};

export const conflictResolutionDrafts = {
  load: (id: string, namespace = 'file') => loadJson<ConflictResolutionDraft>(scopedKey('conflict-resolution', id, namespace)),
  save: (value: ConflictResolutionDraft, namespace = 'file') =>
    storage.setItem(scopedKey('conflict-resolution', value.chapterId, namespace), JSON.stringify(value)),
  remove: (id: string, namespace = 'file') => storage.removeItem(scopedKey('conflict-resolution', id, namespace)),
};

/** User-triggered local export only; prose never enters HTML or a network request. */
export function exportDraftText(content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const revoke = URL.revokeObjectURL.bind(URL);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'writing-recovery.txt';
  document.body.append(link);
  try { link.click(); } finally {
    link.remove();
    setTimeout(() => revoke(url), 0);
  }
}
