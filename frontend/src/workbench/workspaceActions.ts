/**
 * [HERMIA-FE-20261022] Overflow module discoverability (CONTROL / PLUGIN / WORKFLOW).
 * Not on default chrome; reachable via CommandSearch / ActionRegistry.
 * Does not invent backend — only navigates ModuleSwitcher targets.
 */
import type {ActionRegistry} from './actions';
import type {StudioModule} from '../ui/moduleRegistry';

const OVERFLOW: Array<{id: string; label: string; module: StudioModule}> = [
  {id: 'workspace.open.control', label: '打开：AI 主控（模型 / Provider）', module: 'CONTROL'},
  {id: 'workspace.open.plugin', label: '打开：插件管理', module: 'PLUGIN'},
  {id: 'workspace.open.workflow', label: '打开：工作流编排工作区', module: 'WORKFLOW'},
  {id: 'workspace.open.edit', label: '打开：剪辑（多轨 NLE）', module: 'EDIT'},
  {id: 'workspace.open.video', label: '打开：视频工作区（三层）', module: 'VIDEO'},
  {id: 'workspace.open.image', label: '打开：图片工作区', module: 'IMAGE'},
  {id: 'workspace.open.audio', label: '打开：声音工作区', module: 'AUDIO'},
  {id: 'workspace.open.assets', label: '打开：资产浏览器', module: 'ASSETS'},
];

export function registerWorkspaceModuleActions(
  actions: ActionRegistry,
  openModule: (module: StudioModule) => void,
): () => void {
  const undo: Array<() => void> = [];
  for (const a of OVERFLOW) {
    undo.push(actions.register({
      id: a.id,
      label: a.label,
      surfaces: ['commandSearch', 'button'],
      run: async () => {
        openModule(a.module);
        return a.module;
      },
    }));
  }
  return () => undo.reverse().forEach(f => f());
}
