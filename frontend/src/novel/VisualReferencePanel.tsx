import { useEffect, useState } from "react";
import { api, apiErrorView, type Asset, type AssetReferences, type VisualReference, type VisualReferenceSearch } from "../api";
import { Button, StatusMessage } from "../ui/primitives";

/** Explicit user-reviewed reference metadata. No inference or embedding claims. */
export function VisualReferencePanel({ asset }: { asset: Asset }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [references, setReferences] = useState<AssetReferences>();
  const [memories, setMemories] = useState<VisualReference[]>([]);
  const [entityType, setEntityType] = useState("STYLE");
  const [entityId, setEntityId] = useState("");
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VisualReferenceSearch>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true); setError(undefined);
    Promise.all([api.assetReferences(asset.novel_id, asset.id), api.visualReferences(asset.novel_id, asset.id)])
      .then(([refs, memory]) => { if (active) { setReferences(refs); setMemories(memory.items); } })
      .catch(reason => { if (active) setError(reason); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, reload, asset.id, asset.novel_id]);

  async function act(operation: () => Promise<unknown>) {
    setBusy(true); setError(undefined);
    try { await operation(); setReload(value => value + 1); }
    catch (reason) { setError(reason); }
    finally { setBusy(false); }
  }
  return <details className="visual-reference-panel" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>参考记忆与引用</summary>
    <p className="novel-help">本地关键词检索，仅使用手工审核通过的参考说明。未启用图像语义或 embedding 模型。</p>
    {loading && <p role="status">正在读取引用…</p>}
    {Boolean(error) && <StatusMessage tone="error">{apiErrorView(error, "参考记忆操作失败，请重试。").message}</StatusMessage>}
    {Boolean(error) && <Button variant="ghost" disabled={busy || loading} onClick={() => setReload(value => value + 1)}>重新读取引用</Button>}
    {references && <p className="novel-help">已记录 {references.total} 个引用，覆盖参考记忆、研究资料、派生关系和资产来源。其他模块引用未扫描。</p>}
    {references && references.items.length > 0 && <ul>{references.items.map(item => <li key={`${item.collection}:${item.id}:${item.field}`}>
      {item.collection} · {item.id} · v{item.version}
    </li>)}</ul>}
    {asset.media_type.startsWith("image/") && <>
      <form onSubmit={event => { event.preventDefault(); void act(async () => {
        await api.createVisualReference(asset.novel_id, { entity_type: entityType, entity_id: entityId.trim(), asset_id: asset.id, notes: notes.trim(), origin: "USER" });
        setNotes(""); setResults(undefined);
      }); }}>
        <label>参考类型<select aria-label="参考类型" value={entityType} disabled={busy} onChange={event => setEntityType(event.target.value)}>
          <option value="STYLE">风格</option><option value="CHARACTER">角色</option><option value="LOCATION">地点</option><option value="SCENE">场景</option><option value="OTHER">其他</option>
        </select></label>
        <label>实体 ID<input aria-label="参考实体 ID" required maxLength={240} value={entityId} disabled={busy} onChange={event => setEntityId(event.target.value)}/></label>
        <label>参考说明<textarea aria-label="参考说明" required maxLength={10000} value={notes} disabled={busy} onChange={event => setNotes(event.target.value)}/></label>
        <Button type="submit" variant="primary" disabled={busy || !entityId.trim() || !notes.trim()}>{busy ? "处理中…" : "保存待审核参考"}</Button>
      </form>
      {memories.length === 0 && !loading && !error && <p className="novel-help">当前图片还没有参考记忆。</p>}
      {memories.map(memory => <article key={memory.id}>
        <p>{memory.entity_type} · {memory.entity_id} · v{memory.version}</p><p>{memory.notes}</p>
        {memory.approval_status === "APPROVED" && <p role="status">已审核。检索时仍会验证资产摘要与版本。</p>}
        <Button variant="ghost" disabled={busy || memory.status !== "ACTIVE"} onClick={() => void act(async () => {
          await api.approveVisualReference(asset.novel_id, memory.id, memory.version); setResults(undefined);
        })}>{memory.approval_status === "APPROVED" ? "重新审核当前版本" : "审核通过并索引"}</Button>
      </article>)}
    </>}
    <form onSubmit={event => { event.preventDefault(); void act(async () => setResults(await api.searchVisualReferences(asset.novel_id, query.trim()))); }}>
      <label>检索已审核参考<input aria-label="检索已审核参考" maxLength={1000} value={query} disabled={busy} onChange={event => setQuery(event.target.value)}/></label>
      <Button type="submit" variant="ghost" disabled={busy}>检索参考</Button>
    </form>
    {results && <div aria-live="polite">
      <p>已索引 {results.indexed_count} 条，匹配 {results.total} 条。</p>
      {results.excluded.length > 0 && <StatusMessage tone="warning">{results.excluded.length} 条参考因资产缺失、损坏或审核版本过期被排除，请检查原素材并重新审核。</StatusMessage>}
      {results.items.map(item => <article key={item.id}>
        <p>{item.entity_type} · {item.entity_id} · v{item.version}</p>
        <p className="novel-help">参考 {item.id} · 资产 {item.asset_id} · SHA-256 {item.provenance.asset_sha256.slice(0, 12)}</p>
        <p>匹配词：{item.matched_terms.join("、") || "全部已审核参考"}</p>
      </article>)}
    </div>}
  </details>;
}
