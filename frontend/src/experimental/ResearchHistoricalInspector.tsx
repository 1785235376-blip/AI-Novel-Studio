import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ExperimentalClient } from './api';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import { researchLibraryClient, type Citation, type HistoricalInspection, type Source } from './researchLibraryClient';
import { sameResearchCitation } from './researchEvidenceLocation';

/** Read-only historical data, intentionally isolated from current citation selection. */
export function ResearchHistoricalInspector({ client, source, revisions }: { client: ExperimentalClient; source: Source; revisions: Source[] }) {
  const api = useMemo(() => researchLibraryClient(client), [client]);
  const [version, setVersion] = useState('');
  const [paragraph, setParagraph] = useState('1');
  const [page, setPage] = useState('');
  const [hash, setHash] = useState('');
  const [result, setResult] = useState<HistoricalInspection>();
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const revisionIdentity = JSON.stringify(revisions.map(row => [row.id, row.version, row.status]));
  const epoch = useRef(0), request = useRef<AbortController>();
  const clear = () => { ++epoch.current; request.current?.abort(); setResult(undefined); setNotice(''); setBusy(false); };
  useLayoutEffect(() => {
    clear(); setVersion(''); setParagraph('1'); setPage(''); setHash('');
    return () => { ++epoch.current; request.current?.abort(); };
  }, [api, source.id, source.version, source.status, revisionIdentity]);
  const valid = source.status === 'ACTIVE' && revisions.some(row => row.id === source.id && row.version === Number(version) && row.status === 'ACTIVE' && row.version < source.version)
    && /^\d+$/.test(paragraph) && Number(paragraph) <= 5000 && /^[a-f0-9]{64}$/.test(hash)
    && (Number(paragraph) !== 0 || (/^\d+$/.test(page) && Number(page) >= 1 && Number(page) <= 1000));
  const inspect = async () => {
    if (!valid) return;
    clear(); const ticket = epoch.current; const controller = new AbortController(); request.current = controller; setBusy(true);
    const ref: Citation = { source_id: source.id, source_version: Number(version), paragraph: Number(paragraph), quote_sha256: hash, ...(Number(paragraph) === 0 ? { page: Number(page) } : {}) };
    try {
      const value = await api.inspectHistory(ref, source.version, controller.signal);
      if (ticket !== epoch.current || controller.signal.aborted) return;
      if (!value || value.historical_only !== true || value.usable_as_current_evidence !== false || value.current_version !== source.version
          || !value.historical_citation || !sameResearchCitation(ref, value.historical_citation)
          || !(value.page === null || (Number.isInteger(value.page) && Number(value.page) >= 1 && Number(value.page) <= 1000))
          || typeof value.text !== 'string' || value.text.length > 8000 || value.not_understood !== (ref.paragraph === 0)
          || (ref.paragraph === 0 && (value.text !== '' || value.page !== ref.page))) throw new Error('Unverified history');
      setResult(value);
    } catch {
      if (ticket === epoch.current && !controller.signal.aborted) setNotice('历史位置不可核对。请检查原引用摘要、版本与当前来源权限；未读取其他版本。');
    } finally { if (ticket === epoch.current) setBusy(false); }
  };
  return <section className="experimental-record" aria-label="历史原文只读核对">
    <h4>历史原文只读核对</h4>
    <p>输入原引用中的位置与 SHA-256 摘要，明确读取一个历史段落。历史文字不恢复旧引用，也不会进入笔记、上下文或设定草稿。</p>
    <form className="experimental-form" onSubmit={event => { event.preventDefault(); void inspect(); }}>
      <Field label="核对历史版本"><select value={version} onChange={event => { clear(); setVersion(event.target.value); }}><option value="">选择历史版本</option>{revisions.filter(row => row.id === source.id && row.status === 'ACTIVE' && row.version < source.version).map(row => <option key={row.version} value={row.version}>v{row.version}</option>)}</select></Field>
      <Field label="原引用段落编号（页面引用填 0）"><input inputMode="numeric" maxLength={4} value={paragraph} onChange={event => { clear(); setParagraph(event.target.value); }} /></Field>
      {Number(paragraph) === 0 && <Field label="原引用页码"><input inputMode="numeric" maxLength={4} value={page} onChange={event => { clear(); setPage(event.target.value); }} /></Field>}
      <Field label="原引用 SHA-256 摘要"><input maxLength={64} value={hash} onChange={event => { clear(); setHash(event.target.value); }} /></Field>
      <Button type="submit" disabled={!valid || busy}>只读核对历史位置</Button>
      {busy && <><span role="status">正在核对历史位置…</span><Button type="button" onClick={clear}>取消历史核对</Button></>}
    </form>
    {notice && <StatusMessage tone="warning">{notice}</StatusMessage>}
    {result && <section aria-label="历史纯文本"><p>历史版本 v{result.historical_citation.source_version} · {result.not_understood ? `第 ${result.page} 页（未解析）` : `第 ${result.historical_citation.paragraph} 段`} · 只读</p><p>{result.not_understood ? '仅保存页面引用；没有提取文字或页面理解证明。' : result.text}</p><p>原引用摘要：{result.historical_citation.quote_sha256}</p></section>}
  </section>;
}
