/**
 * [HERMIA-FE-20261022 W-UX-15] VIDEO director-layer pin (session contract).
 * User 钉住/收起 survives module hops back to VIDEO. Tab-scoped only.
 * Does not touch Dot write/adopt; does not invent NLE state.
 */
export const VIDEO_DIRECTOR_PIN_KEY = 'poemseed.video.director.pin.v1';

export interface VideoDirectorPin {
  /** Whether layer ③ is open. */
  open: boolean;
  /** True after the author explicitly toggled; then shellMode must not clobber. */
  userSet: boolean;
}

type PinMap = Record<string, VideoDirectorPin>;

function safeParse(raw: string | null): PinMap {
  if (!raw) return {};
  try {
    const value = JSON.parse(raw) as unknown;
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const out: PinMap = {};
    for (const [novelId, row] of Object.entries(value as Record<string, unknown>)) {
      if (!novelId || !row || typeof row !== 'object') continue;
      const r = row as Record<string, unknown>;
      if (typeof r.open !== 'boolean' || typeof r.userSet !== 'boolean') continue;
      out[novelId] = {open: r.open, userSet: r.userSet};
    }
    return out;
  } catch {
    return {};
  }
}

function readAll(): PinMap {
  try {
    return safeParse(globalThis.sessionStorage?.getItem(VIDEO_DIRECTOR_PIN_KEY) ?? null);
  } catch {
    return {};
  }
}

function writeAll(map: PinMap): void {
  try {
    globalThis.sessionStorage?.setItem(VIDEO_DIRECTOR_PIN_KEY, JSON.stringify(map));
  } catch {
    /* session-only; ignore quota / private mode */
  }
}

export function readVideoDirectorPin(novelId: string): VideoDirectorPin | null {
  if (!novelId) return null;
  return readAll()[novelId] ?? null;
}

/** Resolve open state: user pin wins; else shellMode default (pro → open). */
export function resolveVideoDirectorOpen(
  novelId: string,
  shellMode: 'basic' | 'pro',
): {open: boolean; source: 'session' | 'shellMode'} {
  const pin = readVideoDirectorPin(novelId);
  if (pin?.userSet) return {open: pin.open, source: 'session'};
  return {open: shellMode === 'pro', source: 'shellMode'};
}

/** Persist an explicit author toggle (钉住 / 收起). */
export function writeVideoDirectorPin(novelId: string, open: boolean): VideoDirectorPin {
  const pin: VideoDirectorPin = {open, userSet: true};
  if (!novelId) return pin;
  const next = {...readAll(), [novelId]: pin};
  writeAll(next);
  return pin;
}

export function clearVideoDirectorPins(): void {
  try {
    globalThis.sessionStorage?.removeItem(VIDEO_DIRECTOR_PIN_KEY);
  } catch {
    /* ignore */
  }
}
