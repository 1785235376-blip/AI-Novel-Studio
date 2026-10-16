/** Read-only, positional comparison of the existing verified revision bodies. */
import { useEffect, useMemo, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { bodyStateLabel } from './PromptLibraryPanel';

export type RevisionDiffSide = {
  revision: number;
  body: { state: string; value: string | null; verified: boolean; readComplete: boolean };
};
type DiffRow = { line: number; left: string | null; right: string | null; changed: boolean };
const PAGE_SIZE = 100;
const complete = (side: RevisionDiffSide) =>
  side.body.state === 'COMPLETE' && side.body.verified && side.body.readComplete;

/** Absence is not an empty line: adding/removing a newline is a real text change. */
function lineRows(before: string, after: string): DiffRow[] {
  const left = before.split('\n');
  const right = after.split('\n');
  return Array.from({ length: Math.max(left.length, right.length) }, (_, index) => ({
    line: index + 1,
    left: left[index] ?? null,
    right: right[index] ?? null,
    changed: left[index] !== right[index],
  }));
}

function LineValue({ value }: { value: string | null }) {
  if (value === null) return <span className="prompt-diff-placeholder" aria-label="此修订没有该行">无此行</span>;
  if (value === '') return <span className="prompt-diff-placeholder" aria-label="该行为空">空行</span>;
  return <>{value}</>;
}

export function RevisionDiff({ from, to, professional }: {
  from: RevisionDiffSide; to: RevisionDiffSide; professional: boolean;
}) {
  const [changesOnly, setChangesOnly] = useState(false);
  const [page, setPage] = useState(0);
  const comparable = complete(from) && complete(to);
  const rows = useMemo(() => comparable ? lineRows(from.body.value ?? '', to.body.value ?? '') : [],
    [comparable, from.body.value, to.body.value]);
  const changedRows = useMemo(() => rows.filter(row => row.changed), [rows]);
  const visibleRows = changesOnly ? changedRows : rows;
  const pages = Math.max(1, Math.ceil(visibleRows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const offset = currentPage * PAGE_SIZE;
  const pageRows = visibleRows.slice(offset, offset + PAGE_SIZE);

  useEffect(() => { setPage(0); }, [from.revision, to.revision, from.body.value, to.body.value, changesOnly]);

  // Keep the existing complete/verified/readComplete boundary. A preview or digest
  // never becomes comparison text, and pagination performs no additional read.
  if (!comparable) {
    const blocked = [from, to].filter(side => !complete(side))
      .map(side => `修订 ${side.revision}：${bodyStateLabel(side.body.state)}`
        + (side.body.state === 'COMPLETE' ? '（未通过完整性校验）' : ''))
      .join('；');
    return <StatusMessage tone="warning">
      无法比较完整正文：{blocked}。只有完整且通过校验的正文才能做正文差异比较。
    </StatusMessage>;
  }

  return (
    <div className="prompt-diff">
      <p>修订 {from.revision} → 修订 {to.revision}：{changedRows.length} 行不同（共 {rows.length} 行）。</p>
      <p className="prompt-diff-limit">按相同行号对照；插入或删除内容可能使后续行号错位，不自动对齐文本。空行与无此行分别标注。</p>
      <div className="prompt-diff-controls">
        <label><input type="checkbox" checked={changesOnly}
          onChange={event => { setChangesOnly(event.target.checked); setPage(0); }} />仅显示差异行</label>
      </div>
      {visibleRows.length === 0 ? <StatusMessage>两个修订没有正文行差异。</StatusMessage> : <>
        <nav className="prompt-diff-controls" aria-label="版本差异分页">
          <Button disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>上一页差异</Button>
          <span role="status">第 {currentPage + 1} / {pages} 页，显示第 {offset + 1}–{offset + pageRows.length} 项（共 {visibleRows.length} 项）；每页最多 {PAGE_SIZE} 行。</span>
          <Button disabled={currentPage === pages - 1} onClick={() => setPage(currentPage + 1)}>下一页差异</Button>
        </nav>
        <table>
          <caption className="sr-only">两个修订的正文逐行差异</caption>
          <thead><tr><th scope="col">行</th><th scope="col">修订 {from.revision}</th><th scope="col">修订 {to.revision}</th></tr></thead>
          <tbody>{pageRows.map(row => <tr key={row.line} className={row.changed ? 'prompt-diff-changed' : undefined}>
            <td>{row.line}</td><td><LineValue value={row.left} /></td><td><LineValue value={row.right} /></td>
          </tr>)}</tbody>
        </table>
      </>}
      <p className="prompt-diff-limit">
        只比较正文。当前历史读取接口未提供旧版的 negative prompt、模型偏好、参数与引用，
        因此这些字段标注为“历史元数据不可比较”，不会用最新版本反推旧版本。
      </p>
      {professional && <p>两侧均为完整且已校验的正文；渲染时未写入任何日志。</p>}
    </div>
  );
}
