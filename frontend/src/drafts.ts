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

const memory = new Map<string, string>();
const storage = {
  getItem: (key: string) =>
    typeof localStorage === 'undefined' ? memory.get(key) ?? null : localStorage.getItem(key),
  setItem: (key: string, value: string) =>
    typeof localStorage === 'undefined' ? void memory.set(key, value) : localStorage.setItem(key, value),
  removeItem: (key: string) =>
    typeof localStorage === 'undefined' ? void memory.delete(key) : localStorage.removeItem(key),
};

const scopedKey = (kind: string, id: string, namespace = 'file') =>
  `ai-novel-studio:${kind}:${namespace}:${id}`;

function loadJson<T>(key: string): T | undefined {
  try {
    const value = storage.getItem(key);
    return value ? (JSON.parse(value) as T) : undefined;
  } catch {
    return undefined;
  }
}

export const drafts = {
  load: (id: string, namespace = 'file') => loadJson<LocalDraft>(scopedKey('draft', id, namespace)),
  save: (value: LocalDraft, namespace = 'file') =>
    storage.setItem(scopedKey('draft', value.chapterId, namespace), JSON.stringify(value)),
  remove: (id: string, namespace = 'file') => storage.removeItem(scopedKey('draft', id, namespace)),
};

const sameConflict = (left: PersistentConflict, right: PersistentConflict) =>
  left.detectedAt === right.detectedAt &&
  left.local.updatedAt === right.local.updatedAt &&
  left.server.version === right.server.version;

export const conflicts = {
  load: (id: string, namespace = 'file') =>
    loadJson<PersistentConflict>(scopedKey('conflict', id, namespace)),
  list: (id: string, namespace = 'file') =>
    loadJson<PersistentConflict[]>(scopedKey('conflict-history', id, namespace)) ?? [],
  save(value: PersistentConflict, namespace = 'file') {
    const current = this.load(value.chapterId, namespace);
    const history = this.list(value.chapterId, namespace);
    if (current && !sameConflict(current, value) && !history.some(item => sameConflict(item, current))) {
      history.push(current);
      storage.setItem(scopedKey('conflict-history', value.chapterId, namespace), JSON.stringify(history));
    }
    storage.setItem(scopedKey('conflict', value.chapterId, namespace), JSON.stringify(value));
  },
  remove: (id: string, namespace = 'file') => storage.removeItem(scopedKey('conflict', id, namespace)),
  clearHistory: (id: string, namespace = 'file') =>
    storage.removeItem(scopedKey('conflict-history', id, namespace)),
};

export const conflictResolutionDrafts = {
  load: (id: string, namespace = 'file') =>
    loadJson<ConflictResolutionDraft>(scopedKey('conflict-resolution', id, namespace)),
  save: (value: ConflictResolutionDraft, namespace = 'file') =>
    storage.setItem(scopedKey('conflict-resolution', value.chapterId, namespace), JSON.stringify(value)),
  remove: (id: string, namespace = 'file') =>
    storage.removeItem(scopedKey('conflict-resolution', id, namespace)),
};
