import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import { createProjectGraphTemplate, planProjectGraphTemplate, readProjectGraphTemplate, PROJECT_GRAPH_TEMPLATE_BYTES } from './graphProjectTemplates';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
type Props = { definition: StudioGraphDefinition; base?: StudioGraphRecord; selected: string[]; catalog: StudioGraphCatalog; owner?: StudioGraphDraftOwner; fenceOwner: object; disabled: boolean; isCurrent: () => boolean;
  readSource: (id: string) => Promise<StudioGraphRecord>; onApply: (definition: StudioGraphDefinition, selected: string[]) => void };
type Candidate = ReturnType<typeof planProjectGraphTemplate> & { token: object };
export function GraphProjectTemplateTools(props: Props) {
  const [candidate, setCandidate] = useState<Candidate>(), [busy, setBusy] = useState(false), [error, setError] = useState(''), [, rerender] = useState(0);
  const alive = useRef(true), active = useRef(false), ticket = useRef(0), live = useRef(props); live.current = props;
  const input = useRef<HTMLInputElement>(null), exportConsent = useRef<{ token: object; checked: boolean }>(), importConsent = useRef<{ candidate: Candidate; checked: boolean }>();
  const values = [props.definition, props.base, JSON.stringify(props.selected), JSON.stringify(props.catalog), JSON.stringify(props.owner), props.fenceOwner, props.disabled], fence = useRef({ values, token: {} });
  if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {} };
  const token = fence.current.token, current = () => alive.current && fence.current.token === token && !!live.current.owner && !live.current.disabled && live.current.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; ticket.current++; }; }, []);
  useLayoutEffect(() => { ticket.current++; setCandidate(undefined); setError(''); exportConsent.current = undefined; importConsent.current = undefined; if (input.current) input.current.value = ''; }, [token]);
  const visible = candidate?.token === token ? candidate : undefined;
  const canExport = !!props.base && !!props.selected.length && JSON.stringify(props.definition) === JSON.stringify(props.base.definition);
  async function exportFile() {
    if (!current() || active.current || !canExport || !props.base || exportConsent.current?.token !== token || !exportConsent.current.checked) return;
    exportConsent.current = undefined; active.current = true; setBusy(true); setError(''); const request = ++ticket.current;
    try { const source = await props.readSource(props.base.id); if (!current() || ticket.current !== request) return;
      if (source.version !== props.base.version || source.definition_digest !== props.base.definition_digest || source.execution_digest !== props.base.execution_digest || source.id !== props.base.id) throw new Error('原保存图已经变化。');
      const raw = createProjectGraphTemplate(source, props.selected, props.owner!); if (current()) downloadPortableBlob(new Blob([raw], { type: 'application/json' }), 'poemseed-project-graph-reference.json');
    } catch { if (current()) setError('当前保存图或来源权限未通过核对，未导出引用模板。'); }
    finally { active.current = false; if (alive.current) setBusy(false); }
  }
  async function load(file?: File) {
    if (!file || !current() || active.current) return; active.current = true; setBusy(true); setError(''); setCandidate(undefined); importConsent.current = undefined; const request = ++ticket.current;
    try { if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > PROJECT_GRAPH_TEMPLATE_BYTES) throw new Error('文件过大。');
      const raw = await file.text(); if (!current() || ticket.current !== request) return;
      const template = readProjectGraphTemplate(raw, props.owner!); const source = await props.readSource(template.source.id); if (!current() || ticket.current !== request) return;
      const plan = planProjectGraphTemplate(template, source, props.definition, props.catalog, props.owner!); if (current()) setCandidate({ ...plan, token });
    } catch { if (current()) setError('引用模板核对失败：必须属于当前项目实例、身份及分支，且原图版本和素材来源仍有效。不会自动改绑或升级格式。'); }
    finally { active.current = false; if (alive.current) setBusy(false); }
  }
  function apply() { if (!current() || active.current || !visible || importConsent.current?.candidate !== visible || !importConsent.current.checked) return; importConsent.current = undefined; setCandidate(undefined); ticket.current++; props.onApply(visible.result.definition, visible.result.selected); }
  return <section aria-label="同项目图引用模板"><h4>同项目图引用模板</h4><p>支持原图中的多模态节点。文件只保存当前身份、项目实例、原图版本和节点 ID，不保存正文、媒体、令牌或执行许可。使用时重新读取原图；原图变化、跨项目或权限失效会拒绝导入。</p>
    {!props.owner && <StatusMessage>需先核对项目实例和身份，才能使用持久引用模板。</StatusMessage>}
    <label><input type="checkbox" checked={exportConsent.current?.token === token && exportConsent.current.checked || false} disabled={props.disabled || !props.owner || !canExport || busy} onChange={event => { exportConsent.current = { token, checked: event.target.checked }; rerender(v => v + 1); }} />确认把已保存图的所选节点版本引用导出到本地</label>
    <Button disabled={props.disabled || !props.owner || !canExport || busy || exportConsent.current?.token !== token || !exportConsent.current.checked} onClick={() => void exportFile()}>核对并导出项目引用模板</Button>
    <label>导入同项目图引用 JSON<input ref={input} type="file" accept="application/json,.json" disabled={props.disabled || !props.owner || busy} onChange={event => void load(event.target.files?.[0])} /></label>
    {busy && <StatusMessage>正在核对原图版本与来源…</StatusMessage>}{visible && <div><p>原图 {visible.sourceId} · v{visible.sourceVersion}。将追加 {visible.result.nodeCount} 个节点和 {visible.result.edgeCount} 条内部连接；保留原绑定，使用新节点 ID。保存时仍由原后端重新核对。</p>
      <label><input type="checkbox" checked={importConsent.current?.candidate === visible && importConsent.current.checked || false} disabled={props.disabled} onChange={event => { importConsent.current = { candidate: visible, checked: event.target.checked }; rerender(v => v + 1); }} />确认只把已核对的引用模板追加到当前草稿</label>
      <Button disabled={props.disabled || importConsent.current?.candidate !== visible || !importConsent.current.checked} onClick={apply}>明确追加项目引用节点</Button></div>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
