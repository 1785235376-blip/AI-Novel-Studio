import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
import { Details, Field, ResourceState, objectValue, useAction, useResource } from './shared';
import { templateLibraryClient, type TemplateComparison, type TemplateInstance, type TemplatePackage, type TemplatePreview } from './templateLibraryClient';
let sequence = 0;
const requestId = () => globalThis.crypto.randomUUID();
const labels: Record<string, string> = { planning: '章节结构', character: '人物档案', screenplay: '剧本', storyboard: '分镜', review: '审核流程', workflow: 'Workflow' };
export function TemplateLibraryPanel(props: { client: ExperimentalClient; onNavigate?: (value: WorkspaceNavigation) => void }) {
  const key = useMemo(() => ++sequence, [props.client]); return <LibraryBody key={key} {...props} />;
}
function PackagePreview({ value }: { value: TemplatePackage }) {
  const sections = value.content.sections as { key: string; title: string; text: string }[] | undefined;
  return <figure className="experimental-record" aria-label="模板结构预览">
    <figcaption>{value.manifest.title} · {labels[value.manifest.type]} · {value.manifest.version}</figcaption>
    <p>{value.manifest.description}</p>
    {sections?.map(section => <p key={section.key}><strong>{section.title}</strong>：{section.text}</p>)}
    {value.content.beats && <ul>{Object.entries(value.content.beats).map(([key, text]) => <li key={key}>{key}：{String(text)}</li>)}</ul>}
    {value.content.nodes && <ol>{value.content.nodes.map((node: { id: string; name: string; type: string }) => <li key={node.id}>{node.name} · {node.type}</li>)}</ol>}
    <p>作者：{value.manifest.author} · 许可声明：{value.manifest.license}</p>
    <p>依赖：{value.manifest.dependencies.join('、') || '无'} · 来源：{value.manifest.provenance}</p>
  </figure>;
}
function LibraryBody({ client, onNavigate }: { client: ExperimentalClient; onNavigate?: (value: WorkspaceNavigation) => void }) {
  const api = useMemo(() => templateLibraryClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]);
  const copies = useResource(signal => api.instances(signal), [api]);
  const [selected, setSelected] = useState(''), [type, setType] = useState(''), [favorites, setFavorites] = useState(false);
  const [raw, setRaw] = useState(''), [preview, setPreview] = useState<TemplatePreview>();
  const [copy, setCopy] = useState<TemplateInstance>(), [edit, setEdit] = useState('');
  const [compare, setCompare] = useState<TemplateComparison>(), [overwrite, setOverwrite] = useState(false);
  const [history, setHistory] = useState<{ version: number; package_version: string; content: unknown }[]>([]), [restore, setRestore] = useState('');
  const [confirmUninstall, setConfirmUninstall] = useState(false);
  const alive = useRef(true), epoch = useRef(0), importEpoch = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; importEpoch.current++; }; }, []);
  const action = useAction();
  const available = catalog.data?.items.filter(row => (!type || row.package.manifest.type === type) && (!favorites || row.favorite)) || [];
  const entry = available.find(row => row.id === selected);
  const chooseCopy = (row?: TemplateInstance) => { epoch.current++; setCopy(row); setEdit(row ? JSON.stringify(row.content, null, 2) : ''); setCompare(undefined); setHistory([]); setRestore(''); setOverwrite(false); };
  const acceptCopy = (row: TemplateInstance, ticket: number) => { if (alive.current && epoch.current === ticket) { chooseCopy(row); copies.reload(); } };
  return <section className="experimental-section" aria-label="本地模板库">
    <div className="experimental-actions"><h3>本地模板库</h3><Badge>离线 · 声明式数据</Badge><Button disabled={action.busy} onClick={() => { catalog.reload(); copies.reload(); setPreview(undefined); setCompare(undefined); }}>刷新模板目录</Button></div>
    <p>模板安装不运行脚本、不启用工具或模型。只接收不超过 128 KB 的 JSON 目录包；ZIP、外部图片、路径与远程下载均不支持。许可是提供方声明，尚未进行商业法律审核。</p>
    <Panel title="离线目录与预览">
      <ResourceState loading={catalog.loading} error={catalog.error} empty={!catalog.data?.items.length} />
      <div className="experimental-grid"><Field label="模板类型"><select value={type} onChange={e => { setType(e.target.value); setSelected(''); }}><option value="">全部类型</option>{catalog.data?.types.map(t => <option key={t} value={t}>{labels[t] || t}</option>)}</select></Field><label><input type="checkbox" checked={favorites} onChange={e => { setFavorites(e.target.checked); setSelected(''); }} />只看收藏</label></div>
      <Field label="选择本地模板"><select value={selected} disabled={catalog.loading || !!catalog.error || action.busy} onChange={e => { setSelected(e.target.value); setConfirmUninstall(false); }}><option value="">请选择模板</option>{available.map(row => <option value={row.id} key={row.id}>{row.favorite ? '★ ' : ''}{row.package.manifest.title} · {row.package.manifest.version}</option>)}</select></Field>
      {entry && !catalog.loading && !catalog.error && <>
        <PackagePreview value={entry.package} />
        {entry.missing_dependencies.length > 0 && <StatusMessage tone="warning">复制不可用，缺少服务端依赖：{entry.missing_dependencies.join('、')}。可以查看或收藏，不能由模板开启依赖。</StatusMessage>}
        <div className="experimental-actions"><Button disabled={action.busy} onClick={() => action.run(async () => { await api.favorite(entry); catalog.reload(); }, entry.favorite ? '已取消收藏。' : '已收藏。')}>{entry.favorite ? '取消收藏' : '收藏模板'}</Button><Button disabled={action.busy} onClick={() => { importEpoch.current++; setRaw(JSON.stringify(entry.package, null, 2)); setPreview(undefined); }}>填入安装预览</Button><Button disabled={action.busy || entry.missing_dependencies.length > 0} onClick={() => action.run(async () => { const ticket = epoch.current; acceptCopy(await api.copy(entry, requestId()), ticket); }, '已创建独立项目副本，未执行工作流或修改正文。')}>复制为本项目版本</Button></div>
        {entry.installed && <><label><input type="checkbox" checked={confirmUninstall} onChange={e => setConfirmUninstall(e.target.checked)} />仅卸载目录记录，保留全部项目副本与已创建作品</label><Button disabled={action.busy || !confirmUninstall} onClick={() => action.run(async () => { await api.uninstall(entry); catalog.reload(); setConfirmUninstall(false); }, '目录记录已卸载。项目副本保持不变；内置样例仍可离线查看。')}>卸载本地目录记录</Button></>}
      </>}
    </Panel>
    <Panel title="受限 JSON 导入与更新预览">
      <Field label="模板目录 JSON"><textarea rows={8} maxLength={128000} value={raw} onChange={e => { importEpoch.current++; setRaw(e.target.value); setPreview(undefined); }} /></Field>
      <Button disabled={action.busy || !raw.trim()} onClick={() => action.run(async () => { const ticket = importEpoch.current; const result = await api.preview(raw); if (alive.current && ticket === importEpoch.current) setPreview(result); }, '结构与权限边界预检完成。尚未安装。')}>预检并比较目录</Button>
      {preview && <><PackagePreview value={preview.package} /><Details label="安装前差异" value={preview.diff.lines} open />{preview.diff.truncated && <StatusMessage tone="warning">差异超过 500 行，当前仅显示部分内容。</StatusMessage>}{preview.missing_dependencies.length > 0 && <StatusMessage tone="warning">可保存目录，但复制需要：{preview.missing_dependencies.join('、')}</StatusMessage>}<Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = importEpoch.current; await api.install(raw, preview); if (alive.current && ticket === importEpoch.current) setPreview(undefined); catalog.reload(); }, '模板已安装为纯数据。没有执行任何扩展。')}>确认安装这个版本</Button></>}
    </Panel>
    <Panel title="本项目独立副本与回退">
      <ResourceState loading={copies.loading} error={copies.error} empty={!copies.data?.items.length} />
      <Field label="选择项目模板副本"><select value={copy?.id || ''} disabled={action.busy || copies.loading || !!copies.error} onChange={e => chooseCopy(copies.data?.items.find(r => r.id === e.target.value))}><option value="">请选择副本</option>{copies.data?.items.map(row => <option key={row.id} value={row.id}>{row.manifest.title} · 副本 v{row.version}</option>)}</select></Field>
      {copy && <>
        <p>项目副本 {copy.id} · 内容 v{copy.version} · 模板 {copy.package_version}{copy.edited ? ' · 已手工修改' : ''}</p>
        {copy.linked_target && <><p>已独立创建 {copy.linked_target.feature} 记录 {copy.linked_target.id}。下方编辑、更新与回退只改变库中副本，不覆盖已经实例化的规划或 Agent。需要采用新版本时，请再次复制为新记录。</p>{onNavigate && <Button onClick={() => onNavigate({ kind: 'feature', id: copy.linked_target!.id, feature: copy.linked_target!.feature })}>打开已创建记录的功能</Button>}</>}
        {!copy.linked_target && <p>这是可编辑的声明式创作简报，可从下方复制文字使用；尚未写入人物数据库、剧本或正式资产。</p>}
        <Field label="项目副本内容 JSON"><textarea rows={8} value={edit} maxLength={128000} onChange={e => { epoch.current++; setEdit(e.target.value); setCompare(undefined); }} /></Field>
        <div className="experimental-actions"><Button disabled={action.busy || edit === JSON.stringify(copy.content, null, 2)} onClick={() => action.run(async () => { const ticket = epoch.current; acceptCopy(await api.edit(copy, objectValue(edit)), ticket); }, '项目副本已保存，旧版本可恢复。')}>保存副本编辑</Button><Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = epoch.current; const result = await api.compare(copy); if (alive.current && ticket === epoch.current) { setCompare(result); setOverwrite(false); } }, '已比较当前目录版本与已保存副本。')}>比较模板更新</Button><Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = epoch.current; const result = await api.history(copy.id); if (alive.current && ticket === epoch.current) setHistory(result.items); }, '已读取副本历史。')}>查看副本历史</Button></div>
        {compare && <><p>{compare.from_version} → {compare.to_version}。比较以已保存副本为准。</p><Details label="副本更新差异" value={compare.diff.lines} open />{compare.edited && <label><input type="checkbox" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />我确认替换手工编辑的库中副本；旧内容保留在历史中</label>}<Button disabled={action.busy || (compare.edited && !overwrite)} onClick={() => action.run(async () => { const ticket = epoch.current; acceptCopy(await api.update(copy, compare, overwrite), ticket); }, '库中副本已更新；已实例化记录未被覆盖。')}>应用已比较的模板更新</Button></>}
        {history.length > 0 && <><Field label="要恢复的副本历史版本"><select value={restore} onChange={e => setRestore(e.target.value)}><option value="">请选择历史版本</option>{history.map(row => <option key={row.version} value={row.version}>副本 v{row.version} · 模板 {row.package_version}</option>)}</select></Field><Details label="所选历史内容" value={history.find(h => String(h.version) === restore)?.content} /><Button disabled={action.busy || !restore} onClick={() => action.run(async () => { const ticket = epoch.current; acceptCopy(await api.revert(copy, Number(restore)), ticket); }, '已创建恢复版本，未删除历史。')}>恢复为新的副本版本</Button></>}
      </>}
    </Panel>
    {action.feedback}
  </section>;
}
