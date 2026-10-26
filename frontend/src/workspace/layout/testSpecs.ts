// [HERMIA-FE-20261023 M1] Shared test fixtures (test-only).
import type {LayoutPanelSpec} from './model';
export const VP = {width: 1440, height: 900};
export const SPECS: LayoutPanelSpec[] = [
  {id: 'outline', title: '大纲', defaultDock: 'left', docks: ['left', 'right', 'main', 'float'], defaultSize: 248, minSize: 180},
  {id: 'canvas', title: '创作画布', defaultDock: 'main', docks: ['main', 'float'], defaultSize: 800, minSize: 320},
  {id: 'exec', title: '执行画布', defaultDock: 'main', docks: ['main', 'float', 'right'], defaultSize: 800, minSize: 320},
  {id: 'inspector', title: '属性', defaultDock: 'right', docks: ['left', 'right', 'bottom', 'float'], defaultSize: 340, minSize: 240, maxSize: 560},
  {id: 'tasks', title: '任务', defaultDock: 'bottom', docks: ['bottom', 'right', 'left'], defaultSize: 200, minSize: 120},
];
export class MemStorage {
  m = new Map<string, string>(); failSet = false; writes: string[] = [];
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { if (this.failSet) throw new Error('QuotaExceededError'); this.writes.push(k); this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
}
export const SCOPE = {userId: 'u1', projectId: 'p1', projectInstanceId: 'i1'};
