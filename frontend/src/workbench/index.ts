// [HERMIA-FE-20261022] Workbench core contracts (panels/actions/lifecycle/layout). See docs/delivery/HERMIA_FRONTEND_REFACTOR_20261022.md
export * from './lifecycle'; export * from './actions'; export * from './panels'; export * from './layout';
export {registerFeaturePanels} from './featureBridge'; export {registerDemoExtension, DEMO_PANEL_ID} from './demoExtension';
export {isNovelPanel, NOVEL_PANEL_IDS, registerNovelActionAliases, type NovelFocusTarget} from './novelActions';
export {bindRestoreConfirmation, gateRestore, syncRestoreLifecycle, restoreLifecycleContext} from './revisionRestore';
export {registerWorkspaceModuleActions} from './workspaceActions';
