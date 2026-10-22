/**
 * [HERMIA-FE-20261022 W-UX-14] EDIT media-pool handoff inbox (session-only).
 * AUDIO / VIDEO / ASSETS / IMAGE「送去剪辑」push here; EditNleMediaRail reads it.
 * No persistence beyond the tab; no fake green; does not imply writable NLE.
 */
export type EditHandoffSource = 'AUDIO' | 'VIDEO' | 'IMAGE' | 'ASSETS';

export interface EditHandoffItem {
  id: string;
  source: EditHandoffSource;
  label: string;
  novelId?: string;
  at: number;
}

export const EDIT_HANDOFF_STORAGE_KEY = 'poemseed.edit.handoff.v1';

export const EDIT_HANDOFF_SOURCE_LABEL: Record<EditHandoffSource, string> = {
  AUDIO: '声音',
  VIDEO: '视频',
  IMAGE: '图片',
  ASSETS: '资产',
};

function safeParse(raw: string | null): EditHandoffItem[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw) as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter((row): row is EditHandoffItem => {
      if (!row || typeof row !== 'object') return false;
      const r = row as EditHandoffItem;
      return typeof r.id === 'string'
        && typeof r.source === 'string'
        && typeof r.label === 'string'
        && typeof r.at === 'number'
        && (r.source === 'AUDIO' || r.source === 'VIDEO' || r.source === 'IMAGE' || r.source === 'ASSETS');
    });
  } catch {
    return [];
  }
}

export function readEditHandoffs(): EditHandoffItem[] {
  try {
    return safeParse(globalThis.sessionStorage?.getItem(EDIT_HANDOFF_STORAGE_KEY) ?? null);
  } catch {
    return [];
  }
}

export function pushEditHandoff(input: {
  source: EditHandoffSource;
  label: string;
  novelId?: string;
}): EditHandoffItem {
  const item: EditHandoffItem = {
    id: `eh-${input.source.toLowerCase()}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    source: input.source,
    label: input.label,
    novelId: input.novelId,
    at: Date.now(),
  };
  const next = [...readEditHandoffs(), item].slice(-24);
  try {
    globalThis.sessionStorage?.setItem(EDIT_HANDOFF_STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* session-only; ignore quota / private mode */
  }
  return item;
}

export function clearEditHandoffs(): void {
  try {
    globalThis.sessionStorage?.removeItem(EDIT_HANDOFF_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Filter inbox for a project (items without novelId are shared). */
export function editHandoffsForNovel(novelId: string, all = readEditHandoffs()): EditHandoffItem[] {
  return all.filter(h => !h.novelId || h.novelId === novelId);
}
