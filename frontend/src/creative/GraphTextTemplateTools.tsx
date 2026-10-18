import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { exportTextGraphTemplate, planTextGraphTemplate, TEXT_GRAPH_TEMPLATE_BYTES } from './graphTextTemplates';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';
type Props = { definition: StudioGraphDefinition; catalog: StudioGraphCatalog; owner: object; disabled: boolean; isCurrent: () => boolean; onApply: (definition: StudioGraphDefinition, selected: string[]) => void };
type Candidate = ReturnType<typeof planTextGraphTemplate> & { token: object };
export function GraphTextTemplateTools(props: Props) {
  const alive = useRef(true), live = useRef(props); live.current = props;
  const input = useRef<HTMLInputElement>(null), ticket = useRef(0), exportConsent = useRef<{ token: object; checked: boolean }>(), importConsent = useRef<{ candidate: Candidate; checked: boolean }>();
  const [candidate, setCandidate] = useState<Candidate>(), [loading, setLoading] = useState(false), [error, setError] = useState(''), [, renderConsent] = useState(0);
  const values = [props.definition, JSON.stringify(props.catalog), props.owner, props.disabled], fence = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const token = fence.current.token, current = () => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; ticket.current++; }; }, []);
  useLayoutEffect(() => { ticket.current++; setCandidate(undefined); setLoading(false); setError(''); exportConsent.current = undefined; importConsent.current = undefined; if (input.current) input.current.value = ''; }, [token]);
  const visible = candidate?.token === token ? candidate : undefined;
  const exportChecked = exportConsent.current?.token === token && exportConsent.current.checked;
  const importChecked = !!visible && importConsent.current?.candidate === visible && importConsent.current.checked;
  async function read(file?: File) {
    if (!file || !current()) return; const request = ++ticket.current; setCandidate(undefined); importConsent.current = undefined; setLoading(true); setError('');
    try {
      if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > TEXT_GRAPH_TEMPLATE_BYTES) throw new Error('模板文件超出大小限制。');
      const raw = await file.text(); if (!current() || ticket.current !== request) return;
      const plan = planTextGraphTemplate(raw, props.definition, props.catalog); if (current() && ticket.current === request) setCandidate({ ...plan, token });
    } catch { if (current() && ticket.current === request) setError('模板读取或兼容性检查失败。只接受相同格式的受限文字图，不自动转换或放宽原图容量。'); }
    finally { if (alive.current && ticket.current === request) setLoading(false); }
  }
  function exportFile() {
    if (!current() || loading || exportConsent.current?.token !== token || !exportConsent.current.checked) return;
    exportConsent.current = undefined; renderConsent(value => value + 1);
    try { downloadPortableBlob(new Blob([exportTextGraphTemplate(props.definition)], { type: 'application/json' }), 'poemseed-text-graph-template.json'); setError(''); }
    catch { setError('当前图不能导出为文字模板。仅支持不含素材绑定的文字图 v1/v2。'); }
  }
  function apply() {
    if (!current() || !visible || loading || importConsent.current?.candidate !== visible || !importConsent.current.checked) return;
    importConsent.current = undefined; setCandidate(undefined); ticket.current++;
    props.onApply(visible.result.definition, visible.result.selected);
  }
  return <section aria-label="文字图模板复用"><h4>文字图模板</h4><p>仅支持不含素材引用的文字图 v1/v2。模板包含节点文字与内部连接；不携带项目权限、审批、运行结果、分组或便笺。导入仅追加到当前草稿，仍需原保存、预检和执行确认。</p>
    <label><input type="checkbox" disabled={props.disabled || loading} checked={!!exportChecked} onChange={event => { exportConsent.current = { token, checked: event.target.checked }; renderConsent(value => value + 1); }} />确认将当前节点文字导出为本地模板文件</label>
    <Button disabled={props.disabled || loading || !exportChecked || !props.definition.nodes.length} onClick={exportFile}>导出受限文字图模板</Button>
    <label>导入文字图模板 JSON<input ref={input} type="file" accept="application/json,.json" disabled={props.disabled || loading} onChange={event => void read(event.target.files?.[0])} /></label>
    {loading && <StatusMessage>正在读取并核对模板…</StatusMessage>}
    {visible && <div><p>来源标题：{visible.sourceTitle}。将新增 {visible.result.nodeCount} 个节点、{visible.result.edgeCount} 条内部连接；节点与连接会使用新标识，目标图现有内容保持。</p>
      <label><input type="checkbox" disabled={props.disabled} checked={!!importChecked} onChange={event => { importConsent.current = { candidate: visible, checked: event.target.checked }; renderConsent(value => value + 1); }} />确认仅把模板追加到当前本地草稿</label>
      <Button disabled={props.disabled || !importChecked} onClick={apply}>明确追加模板节点</Button></div>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
