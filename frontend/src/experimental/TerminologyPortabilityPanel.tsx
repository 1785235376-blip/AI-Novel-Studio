import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { ErrorMessage, Field } from './shared';
import type { LanguageEdition } from './multilingualEditionsClient';
import { useReviewAction } from './styleReviewClient';
import { readGlossaryFile, terminologyPortabilityClient, glossaryAdmissionToken, startGlossaryAdmission, clearGlossaryAdmission, type GlossaryPreview, type GlossaryReference } from './terminologyPortability';
type Props = { client: ExperimentalClient; edition: LanguageEdition; blocked: boolean; perform: (operation: () => Promise<LanguageEdition>, message: string) => void };
const references = (rows: GlossaryReference[]) => rows.map(row => `${row.kind === 'file' ? '文件' : '当前术语'}第 ${row.index + 1} 行`).join('、');
export function TerminologyPortabilityPanel({ client, edition, blocked, perform }: Props) {
  const api = useMemo(() => terminologyPortabilityClient(client), [client]);
  const action = useReviewAction();
  const [document, setDocument] = useState(''), [filename, setFilename] = useState('');
  const [preview, setPreview] = useState<GlossaryPreview>(), [selected, setSelected] = useState<number[]>([]), [approved, setApproved] = useState(false);
  const [artifact, setArtifact] = useState<{ url: string; filename: string }>(), [uncertain, setUncertain] = useState(() => (glossaryAdmissionToken(client, edition.id) !== undefined));
  const epoch = useRef(0), alive = useRef(true), blockedRef = useRef(blocked), adopting = useRef(false), url = useRef<string>();
  blockedRef.current = blocked;
  const clearDownload = () => { if (url.current) URL.revokeObjectURL(url.current); url.current = undefined; setArtifact(undefined); };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; if (url.current) URL.revokeObjectURL(url.current); }; }, []);
  useLayoutEffect(() => { epoch.current++; setPreview(undefined); setSelected([]); setApproved(false); clearDownload(); }, [edition.id, edition.version, client, blocked]);
  const current = (ticket: number) => alive.current && !blockedRef.current && ticket === epoch.current;
  useLayoutEffect(() => { setUncertain((glossaryAdmissionToken(client, edition.id) !== undefined)); }, [client, edition.id]);
  const disabled = blocked || action.busy || adopting.current || uncertain;
  return <Panel title="复用术语文件">
    <p>仅支持 UTF-8 JSON v1，最大 512 KiB、100 行；本译本最多 100 条规则。术语最多 160 字符、每类别名最多 20 条、备注最多 1000 字符。语言对必须完全相同，保留字面 Unicode，不自动修剪或标准化。</p>
    <p>此文件工具需要原 Studio 项目身份已初始化；若项目尚未在 Studio 打开或身份不可用，导入和下载会停止，不自动创建身份。原有手工术语功能仍可使用。</p>
    <p>保存回执丢失后，重新读取不会取消原请求，也不证明原请求失败。再次导入须重新选择文件、预览并确认；迟到保存仍受原版本检查约束。</p>
    <p>导出包含全部当前术语文字和备注，包括草稿及已撤销规则；不携带批准、锁定或身份信息。导入只新增待批准草稿，不覆盖已有规则。重复或源术语／别名重叠会单独提示。</p>
    <Field label="选择本地术语 JSON 文件"><input type="file" accept=".json,application/json" disabled={disabled} onChange={event => {
      const file = event.target.files?.[0]; event.target.value = ''; if (!file || disabled) return;
      const ticket = ++epoch.current; setDocument(''); setFilename(''); setPreview(undefined); setSelected([]); setApproved(false);
      void action.run(async () => { const text = await readGlossaryFile(file); if (current(ticket)) { setDocument(text); setFilename(file.name); } });
    }} /></Field>
    {filename && <p>已在本地读取：{filename}。本地解析仅供格式检查；检查按钮将原始文本交给当前项目原术语服务，重复 JSON 键等须由服务验证后才可预览。</p>}
    <Button disabled={disabled || !document} onClick={() => {
      const ticket = ++epoch.current; setPreview(undefined); setSelected([]); setApproved(false);
      void action.run(async () => { const result = await api.preview(edition, document); if (current(ticket) && result.edition_version === edition.version) setPreview(result); });
    }}>检查术语导入预览</Button>
    {!blocked && preview && <section aria-label="术语导入预览">
      <p>当前剩余 {preview.remaining_capacity} 条；已选 {selected.length} 条。相同文件重复项仅首项可选；有冲突的行不可导入，请在文件中明确修改后重新检查。</p>
      {preview.entries.length === 0 && <p>文件没有术语行。</p>}
      {preview.entries.map(entry => <article className="experimental-record" key={entry.index}>
        <label><input type="checkbox" disabled={disabled || !entry.eligible} checked={selected.includes(entry.index)} onChange={event => { setApproved(false); setSelected(previous => event.target.checked ? [...previous, entry.index] : previous.filter(index => index !== entry.index)); }} />第 {entry.index + 1} 行：<bdi>{entry.rule.source_term}</bdi> → <bdi>{entry.rule.preferred}</bdi></label>
        <p>类别：{entry.rule.category}；策略：{entry.rule.strategy}；匹配：{entry.rule.match}</p>
        <p>源别名：{entry.rule.source_aliases.join('、') || '无'}；允许译名：{entry.rule.target_aliases.join('、') || '无'}；禁用：{entry.rule.forbidden.join('、') || '无'}；备注：{entry.rule.note || '无'}</p>
        {!!entry.duplicates.length && <StatusMessage>完全重复：{references(entry.duplicates)}</StatusMessage>}
        {!!entry.conflicts.length && <StatusMessage tone="warning">源词或别名冲突：{references(entry.conflicts)}</StatusMessage>}
      </article>)}
      <label><input type="checkbox" disabled={disabled || !selected.length || selected.length > preview.remaining_capacity} checked={approved} onChange={event => setApproved(event.target.checked)} />已核对所选行，仅新增为待批准术语草稿</label>
      <Button disabled={disabled || !approved || !selected.length || selected.length > preview.remaining_capacity} onClick={() => {
        if (adopting.current || blockedRef.current || !approved) return;
        adopting.current = true; const admission = startGlossaryAdmission(client, edition.id); setPreview(undefined); setApproved(false);
        perform(async () => {
          try { const saved = await api.adopt(edition, document, preview, selected); clearGlossaryAdmission(client, edition.id, admission); return saved; }
          catch (error) { if (alive.current) { setUncertain(true); setDocument(''); setFilename(''); } throw error; }
          finally { adopting.current = false; }
        }, '所选术语已原子保存为草稿；请在原术语面板逐项批准，刷新可重新读取。');
      }}>确认导入所选术语草稿</Button>
    </section>}
    {uncertain && <><StatusMessage tone="warning">保存结果未确认。请先重新读取当前语言版本核对已保存术语，再重新选文件检查；不会自动重试。</StatusMessage>
      <Button disabled={blocked || action.busy} onClick={() => {
        const ticket = epoch.current, admission = glossaryAdmissionToken(client, edition.id);
        void action.run(async isCurrent => {
          const fresh = await api.reconcile(edition);
          if (!isCurrent() || !current(ticket)) return;
          if (fresh.id !== edition.id || fresh.stale || fresh.content_withheld || !Array.isArray(fresh.rules)) throw new Error('当前语言版本不可用，仍保留未确认保存状态。');
          if (!clearGlossaryAdmission(client, edition.id, admission)) return;
          setUncertain(false); setDocument(''); setFilename('');
          perform(async () => fresh, '已读取当前术语；旧请求仍可能迟到，请核对后再以新预览明确导入。');
        });
      }}>重新读取并核对术语保存结果</Button></>}
    <Button disabled={disabled} onClick={() => {
      const ticket = ++epoch.current; clearDownload(); setPreview(undefined); setSelected([]); setApproved(false);
      void action.run(async () => { const result = await api.export(edition); if (current(ticket)) { url.current = URL.createObjectURL(new Blob([result.content], { type: result.mime })); setArtifact({ url: url.current, filename: result.filename }); } });
    }}>生成可复用术语 JSON 下载</Button>
    {!blocked && artifact && <a href={artifact.url} download={artifact.filename}>下载术语 JSON 文件</a>}
    {!!action.error && <ErrorMessage error={action.error} />}
  </Panel>;
}
