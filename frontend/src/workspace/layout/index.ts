// [HERMIA-FE-20261023 M1] Unified workspace layout (isolated; not wired into App yet).
export * from './model';
export * from './persistence';
export {useDirtyCloseGuard, type DirtySource, type PendingClose} from './useDirtyCloseGuard';
export {DockLayout, type DockLayoutProps, type PanelRenderApi} from './DockLayout';
