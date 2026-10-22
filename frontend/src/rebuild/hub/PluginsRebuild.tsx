/* [HERMIA-FE-20261022 R7] 插件按原型 pluginsHTML 重写为单页 .ws-full：
   「本地软件」分节（复用 REBUILD-5 LocalInteropPanel，/local-interop/*）+「插件」分节（/api/plugins 列表，行内 启用/停用 走 /plugins/{id}/enable|disable）。
   页主「安装插件…」打开抽屉，里面是原有插件治理面板（/plugin-packages/install 等，安装前先过审核）。后端 execution_supported=false 时如实写明插件还不能运行。 */
import {useCallback, useEffect, useState} from 'react';
import {api} from '../../api';
import {rbError} from '../rebuildApi';
import {Drawer} from '../primitives';
import {LocalInteropPanel} from '../LocalInteropPanel';
import {PluginManagerPanel} from '../../novel/PluginManagerPanel';
import './hubRebuild.css';

/* [HERMIA-FE-20261022 R7-FIX] 默认不信任：后端 v1_capability_service 登记后为 REGISTERED（permission_review=None），
   身份缺失为 REVIEW_REQUIRED（validated=false）；只有 set_plugin_permissions 后的 PERMISSIONS_REVIEWED（带 permission_review、
   所请求权限全部授予）或已激活后停用的 DISABLED（带 permission_review）才允许启用；MANIFEST_ACTIVE 视为已启用。其余一律「未审核」。 */
export function pluginState(p: any): {label: '已启用' | '已安装' | '未审核'; tone: 'ok' | 'part' | 'off'; canEnable: boolean} {
  const status = String(p?.status || '').toUpperCase();
  if (p?.validated !== false && (status === 'MANIFEST_ACTIVE' || (p?.enabled === true && !status))) return {label: '已启用', tone: 'ok', canEnable: false};
  const req: string[] = Array.isArray(p?.requested_permissions) ? p.requested_permissions : [];
  const granted = new Set<string>(Array.isArray(p?.granted_permissions) ? p.granted_permissions : []);
  const reviewed = p?.validated !== false
    && (status === 'PERMISSIONS_REVIEWED' || status === 'DISABLED')
    && !!p?.permission_review && typeof p.permission_review === 'object' && Object.keys(p.permission_review).length > 0 /* [HERMIA-FE-20261022 R7-FIX2] 空 review 视为未审核 */
    && req.every(x => granted.has(x));
  if (!reviewed) return {label: '未审核', tone: 'off', canEnable: false};
  return {label: '已安装', tone: 'part', canEnable: true};
}

export function PluginsRebuild() {
  const [list, setList] = useState<any[] | null>(null);
  const [meta, setMeta] = useState<{exec: boolean} | null>(null);
  const [err, setErr] = useState('');
  const [drawer, setDrawer] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const load = useCallback(() => {
    api.plugins().then((d: any) => { setList(d.items || []); setMeta({exec: !!d.execution_supported}); setErr(''); }).catch(e => { setList([]); setErr(rbError(e)); });
  }, []);
  useEffect(load, [load]);
  async function toggle(p: any) {
    try { const on = pluginState(p).label === '已启用'; await (on ? api.disablePlugin(p.id) : api.enablePlugin(p.id)); setNote(on ? `已停用「${p.name || '插件'}」` : `已启用「${p.name || '插件'}」`); load(); }
    catch (e) { setNote(`操作失败：${rbError(e)}`); }
  }
  return (
    <div className="ws-full hub-ws" data-hub="plugins" aria-label="插件">
      <div className="ws-head"><h2>插件</h2><span className="nv-spacer" />
        <button type="button" className="nv-btn nv-btn--primary" id="plugInstall" onClick={() => setDrawer(true)}>安装插件…</button></div>
      <div className="ws-body plug-hub">
        {note ? <div className="hub-note" role="status">{note}</div> : null}
        <section className="hub-sec" aria-label="本地软件"><h4>本地软件</h4>
          <p className="hub-muted">没连上本机的 ComfyUI 等软件时，图片和视频只能用云端服务。连上后可以用本机算力。连接状态以服务端为准，待核实时不显示已连接。</p>
          <LocalInteropPanel /></section>
        <section className="hub-sec" aria-label="插件列表"><h4>插件</h4>
          {err ? <div className="hub-note hub-note--warn" role="alert">读取插件失败：{err}</div> : null}
          {list === null ? <p className="hub-muted">读取中…</p>
            : list.length === 0 ? <div className="hub-empty" role="status"><p>还没装插件。插件能给各模块加新工具，装之前会先过审核。</p>
              <div className="nv-row"><button type="button" className="nv-btn" onClick={() => setDrawer(true)}>安装插件…</button></div></div>
            : list.map(p => { const s = pluginState(p); return <div key={p.id} className="plug-row-wrap">
              <div className="plug-row"><div className="grow"><b>{p.name || '未命名插件'}</b><div className="hub-muted">{s.label === '未审核' ? '未审核 · 不能启用' : s.label === '已启用' ? '已启用' : '已安装 · 已审核'}{p.version ? ` · 第 ${p.version} 版` : ''}</div></div>
                <span className={`hub-badge hub-badge--${s.tone}`}>{s.label}</span>
                <button type="button" className="nv-btn" onClick={() => setOpen(o => o === p.id ? null : p.id)}>{open === p.id ? '收起' : '设置'}</button>
                <button type="button" className="nv-btn" disabled={s.label !== '已启用' && !s.canEnable} onClick={() => void toggle(p)}>{s.label === '已启用' ? '停用' : '启用'}</button></div>
              {open === p.id ? <div className="plug-detail">{p.description || '这个插件没有写说明。'}{p.permissions ? <> · 权限：{Object.keys(p.permissions).length ? '已按项授权' : '默认全部拒绝'}</> : null}</div> : null}
            </div>; })}
          <div className="hub-note hub-note--warn">未审核、未安装的插件如实标出来，不会显示成可用。{meta && !meta.exec ? '现在后端只做插件登记和审核，插件里的工具还不能真正运行。' : ''}</div>
        </section>
      </div>
      {drawer ? <Drawer title="安装插件" onClose={() => { setDrawer(false); load(); }}><PluginManagerPanel /></Drawer> : null}
    </div>
  );
}
