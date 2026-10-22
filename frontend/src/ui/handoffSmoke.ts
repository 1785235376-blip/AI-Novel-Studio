/**
 * [HERMIA-FE-20261022 X-UX-10] Hand-off smoke contracts (Atlas §0.12).
 * Pure constants — paths exercised by handoffSmoke.xUx10.test.tsx.
 * No fake green; does not change N-UX-04 / EDIT default writable / push.
 */
import type {StudioModule} from './moduleRegistry';

/** Explicit confirm → module switch paths covered by X-UX-10 smoke. */
export const X_UX_10_HANDOFF_PATHS = [
  {from: 'IMAGE', to: 'VIDEO', kind: 'image-ref'} as const,
  {from: 'AUDIO', to: 'EDIT', kind: 'audio-edit'} as const,
  {from: 'ASSETS', to: 'IMAGE', kind: 'assets-send'} as const,
  {from: 'ASSETS', to: 'VIDEO', kind: 'assets-send'} as const,
  {from: 'ASSETS', to: 'AUDIO', kind: 'assets-send'} as const,
  {from: 'ASSETS', to: 'EDIT', kind: 'assets-send'} as const,
] as const;

export type XUx10HandoffPath = (typeof X_UX_10_HANDOFF_PATHS)[number];

/** Modules that must keep shellMode on .app-shell / .media-ws-main across switches. */
export const X_UX_10_SHELL_MODE_MODULES: readonly StudioModule[] = [
  'IMAGE', 'VIDEO', 'AUDIO', 'EDIT', 'ASSETS',
] as const;

/** Copy / markers that must never appear in honest hand-off UX. */
/** Honest copy may say「禁假绿」; forbid readiness claims only. */
export const X_UX_10_FORBIDDEN_READY = /已就绪|已连通绿/;

/** Novel-center markers that media hand-off destinations must not mount. */
export const X_UX_10_NOVEL_CENTER_MARKERS = [
  '.novel-write-chrome',
] as const;
