/**
 * [HERMIA-FE-20261022 X-UX-08] Module switch state isolation (LUMEN_WORKSPACE_ARCH §2.2 / §5).
 * Pure helpers — media/NLE never nest in novel center; return-to-NOVEL restores write 四象限.
 */
import type {StudioModule} from './moduleRegistry';

/** Modules that render via ModuleWorkspaceRoutes (or IndependentStudio), never inside novel center. */
export const MEDIA_OR_TOOL_MODULES: readonly StudioModule[] = [
  'IMAGE', 'VIDEO', 'AUDIO', 'EDIT', 'ASSETS', 'CONTROL', 'PLUGIN', 'WORKFLOW',
] as const;

export const EMPTY_EDITOR_SELECTION = {from: 0, to: 0, text: ''} as const;

/** True when chrome leaves a non-novel workspace and re-enters NOVEL → force write 主面. */
export function shouldRestoreNovelWriteOnEnter(
  previous: StudioModule | undefined,
  next: StudioModule,
): boolean {
  return next === 'NOVEL' && previous !== undefined && previous !== 'NOVEL';
}

/** Novel center must never mount media / NLE shells. */
export function novelCenterAllowsMediaShell(module: StudioModule): boolean {
  return module !== 'NOVEL' ? true : false;
}

/** Active media shell marker for ModuleWorkspaceRoutes (`data-module-shell`). */
export function mediaShellForModule(module: StudioModule): StudioModule | null {
  if (module === 'IMAGE' || module === 'VIDEO' || module === 'AUDIO' || module === 'EDIT' || module === 'ASSETS') {
    return module;
  }
  return null;
}

/** DOM markers that must be absent when `data-module="NOVEL"`. */
export const NOVEL_CENTER_FORBIDDEN_SELECTORS = [
  '.edit-nle-shell',
  '.edit-nle-shell__hero',
  '[data-module-shell="VIDEO"]',
  '[data-module-shell="EDIT"]',
  '[data-module-shell="IMAGE"]',
  '[data-module-shell="AUDIO"]',
  '[data-module-shell="ASSETS"]',
  '.media-ws-main',
] as const;
