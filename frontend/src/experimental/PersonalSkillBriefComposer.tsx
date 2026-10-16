import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import { briefFields, emptyBrief, personalBriefPackage, projectWritingPreset, type BriefIdentity, type PresetSource } from './personalSkillBrief';

type Resource = PresetSource & { name: string };
type Props = { active?: boolean; busy: boolean; onInvalidate: () => void; onPrepare: (text: string) => void; onClose: () => void };
export function PersonalSkillBriefComposer({ active = true, busy, onInvalidate, onPrepare, onClose }: Props) {
  const [identity, setIdentity] = useState<BriefIdentity>({ id: 'personal-', title: '', version: '1.0.0', author: '', license: '' });
  const [text, setText] = useState(emptyBrief), [source, setSource] = useState<PresetSource>();
  const [plugins, setPlugins] = useState<{ id: string; name: string }[]>([]), [plugin, setPlugin] = useState('');
  const [resources, setResources] = useState<Resource[]>([]), [resource, setResource] = useState('');
  const [omitted, setOmitted] = useState<string[]>([]), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);
  const epoch = useRef(0), alive = useRef(true), reading = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useLayoutEffect(() => { if (!active) epoch.current++; }, [active]);
  const changed = () => { epoch.current++; setError(''); setNotice(''); onInvalidate(); };
  const read = async (operation: (ticket: number) => Promise<void>) => {
    if (reading.current || busy) return;
    reading.current = true; changed(); const ticket = epoch.current; setLoading(true);
    try { await operation(ticket); }
    catch { if (alive.current && ticket === epoch.current) setError('来源读取失败、已变更或格式不受支持。未替换简报；请重新读取并核对。'); }
    finally { reading.current = false; if (alive.current) setLoading(false); }
  };
  const current = (ticket: number) => alive.current && epoch.current === ticket;
  return <Panel title="个人写作简报编辑器">
    <p>保存范围是当前用户、当前项目与分支。确定性整理，不调用 AI。内容是审核类简报，可在原模板库收藏、复制、编辑和回退；不会执行预设、改写正文或投稿。</p>
    <div className="experimental-actions"><Button disabled={busy} onClick={() => { changed(); onClose(); }}>关闭简报编辑器</Button><Button disabled={busy || loading} onClick={() => read(async ticket => {
      setPlugins([]); setResources([]); setPlugin(''); setResource('');
      const result = await api.plugins();
      if (current(ticket)) { if (!Array.isArray(result.items) || result.items.some(row => !row || typeof row.id !== 'string' || (row.name !== undefined && typeof row.name !== 'string')) || new Set(result.items.map(row => row.id)).size !== result.items.length) throw new Error('invalid list'); const rows = result.items.filter(row => row.status === 'MANIFEST_ACTIVE' && typeof row.id === 'string'); setPlugins(rows); setNotice(rows.length ? '仅列出已激活清单；发布者字段不是官方认证。请选择后重新校验资源。' : '没有已激活清单。可继续自写；此处不会安装、激活或授予权限。'); }
    })}>读取可用预设包</Button></div>
    <Field label="简报来源包"><select disabled={busy || loading} value={plugin} onChange={event => { changed(); setPlugin(event.target.value); setResources([]); setResource(''); }}><option value="">选择已激活包</option>{plugins.map(row => <option key={row.id} value={row.id}>{row.name || row.id}</option>)}</select></Field>
    <Button disabled={busy || loading || !plugin} onClick={() => read(async ticket => {
      setResources([]); setResource(''); const result = await api.pluginResources(plugin);
      if (!current(ticket)) return;
      if (result.plugin_id !== plugin || result.visible !== true || result.validated !== true || result.validation_status !== 'VALIDATED' || result.status !== 'MANIFEST_ACTIVE' || result.error_code || (result.invalid_resource_count !== undefined && result.invalid_resource_count !== 0) || result.execution_supported !== false || result.isolation !== 'DENY_ALL' || !Array.isArray(result.items) || result.items.some(row => !row || typeof row.resource_id !== 'string' || !row.resource_id || typeof row.kind !== 'string' || (row.name !== undefined && typeof row.name !== 'string')) || (result.resource_count !== undefined && result.resource_count !== result.items.length) || result.total !== result.items.length || new Set(result.items.map(row => row?.resource_id)).size !== result.items.length) throw new Error('unverified');
      const rows = result.items.filter(row => row && row.kind === 'writing_presets' && row.validated === true && typeof row.resource_id === 'string' && /^[a-f0-9]{64}$/.test(row.sha256));
      setResources(rows.map(row => ({ pluginId: plugin, resourceId: row.resource_id, sha256: row.sha256, name: row.name || row.resource_id })));
      if (!rows.length) setNotice('此包没有可用的已验证写作预设。其他资源类型暂不支持。');
    })}>校验并列出写作预设</Button>
    <Field label="简报来源预设"><select disabled={busy || loading} value={resource} onChange={event => { changed(); setResource(event.target.value); }}><option value="">选择写作预设</option>{resources.map(row => <option key={row.resourceId} value={row.resourceId}>{row.name}</option>)}</select></Field>
    <Button disabled={busy || loading || !resource} onClick={() => read(async ticket => {
      const selected = resources.find(row => row.resourceId === resource); if (!selected) return;
      const result = await api.pluginResource(selected.pluginId, selected.resourceId);
      if (!current(ticket)) return;
      const projected = projectWritingPreset(result, selected); onInvalidate(); setText(projected.text); setSource(projected.source); setOmitted(projected.omitted);
      setNotice('已替换下方四项内容。请修改、填写个人身份与许可后再预检；原资源保持不变。');
    })}>读取预设并替换四项内容</Button>
    <p>仅采用用途、写作目标、约束、检查清单。参数提示与其他字段不会成为执行控制，也不自动采用。</p>
    {source && <><p>已采用来源：{source.pluginId} / {source.resourceId} · SHA-256 {source.sha256}。这是已读取内容的引用，不代表发布者认证或后续同步。</p><p>未采用字段：{omitted.join('、') || '无'}</p></>}
    <div className="experimental-grid">{([['id', '个人简报标识'], ['title', '个人简报标题'], ['version', '个人简报版本'], ['author', '个人简报作者'], ['license', '个人简报许可声明']] as const).map(([key, label]) => <Field key={key} label={label}><input disabled={busy || loading} maxLength={key === 'id' ? 80 : 160} value={identity[key]} onChange={event => { changed(); setIdentity({ ...identity, [key]: event.target.value }); }} /></Field>)}</div>
    <p>许可需自行明确填写，不从来源发布者推断；不确定时请先核对。personal- 标识与原包分开，更新内容需递增版本。</p>
    {briefFields.map(([key, label]) => <Field key={key} label={`简报${label}`}><textarea disabled={busy || loading} rows={3} maxLength={8000} value={text[key]} onChange={event => { changed(); setText({ ...text, [key]: event.target.value }); }} /></Field>)}
    <Button disabled={busy || loading} onClick={() => { try { const value = personalBriefPackage(identity, text, source); changed(); onPrepare(JSON.stringify(value, null, 2)); setNotice('已填入下方模板目录 JSON。请预检比较，再确认安装；尚未保存。'); } catch (value) { setError(value instanceof Error ? value.message : '简报无效。'); } }}>填入简报安装预览</Button>
    {loading && <StatusMessage>正在重新读取来源…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
  </Panel>;
}
