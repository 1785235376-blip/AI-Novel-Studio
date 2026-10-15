/**
 * Prompt 工作台（R3-U3-C）。
 *
 * 入口挂在既有 Studio 的素材工作区里，不新增顶层模块、不改受保护外壳。
 * 全部读写都经由 `usePromptWorkspace`（复用 R3-W 写入契约与 R3-U2 正文读取），
 * 组件内不重写任何保存规则。
 */
import { useEffect, useMemo, useState } from 'react';

import type { StudioGraphTransport } from '../creative/studioGraphClient';
import type { StudioInterfaceMode } from '../creative/studioWorkspaceResume';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { PromptEditorPanel } from './PromptEditorPanel';
import { PromptLibraryPanel } from './PromptLibraryPanel';
import { RevisionDiff } from './PromptRevisionDiff';
import { needsRebase } from './promptDraft';
import { usePromptWorkspace } from './usePromptWorkspace';
import './promptWorkspace.css';

export type PromptWorkspaceProps = {
  projectId: string;
  branchId?: string | null;
  actor: string;
  transport: StudioGraphTransport;
  scope?: { projectId?: string } | undefined;
  mode: StudioInterfaceMode;
  writable: boolean;
  denied: boolean;
  onDirtyChange?: (value: boolean) => void;
};

export function PromptWorkspace(props: PromptWorkspaceProps) {
  const { projectId, branchId = null, actor, transport, scope, mode, writable, denied, onDirtyChange } = props;
  const controller = usePromptWorkspace({ projectId, branchId, actor, transport, scope, onDirtyChange });
  const { state, refresh, selectFamily, startNew, edit, save, retry, rebase, discard, compare } = controller;
  const [fromId, setFromId] = useState('');
  const [toId, setToId] = useState('');
  // P0-I: `redacted` is a **display mask** chosen on a revision, not an access control.
  // The authorised body route still serves those bytes (measured), so the default compare
  // UI must not silently reveal a revision the family explicitly marked as masked.
  const [maskNotice, setMaskNotice] = useState<string | null>(null);

  useEffect(() => { void refresh(); /* read the authorised library once the panel mounts */ }, [refresh]);

  const detail = state.detail;
  const versions = detail?.versions ?? [];
  // Default the comparison to the two newest revisions; never invent a revision.
  useEffect(() => {
    if (versions.length < 2) { setFromId(''); setToId(''); return; }
    const sorted = [...versions].sort((a, b) => a.revision - b.revision);
    setFromId(sorted[sorted.length - 2].assetId);
    setToId(sorted[sorted.length - 1].assetId);
  }, [detail?.familyId, versions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const comparison = useMemo(() => state.compare, [state.compare]);
  if (denied) {
    return <Panel title="Prompt 工作台">
      <EmptyState title="当前会话无权访问此项目" detail="重新核对身份与范围后再打开。" />
    </Panel>;
  }

  return (
    <Panel title="Prompt 工作台">
      <p>
        在这里创建和修订手写 Prompt。保存只会新增一个不可变修订，不会覆盖旧版本；
        这里不会调用任何模型，也不会因为输入而自动创建内容。
      </p>

      {/* §1-A: an unsaved draft detected after a reload is *stated*, never "restored".
          Prompt text is deliberately never written to browser storage. */}
      {controller.restoreNotice && (
        <StatusMessage tone="warning">{controller.restoreNotice}</StatusMessage>
      )}

      <div className="prompt-workspace">
        <PromptLibraryPanel
          library={state.library} loading={state.loading} error={state.error}
          selectedFamilyId={detail?.familyId ?? null}
          onSelect={familyId => void selectFamily(familyId)}
          onRefresh={() => void refresh()} onNew={startNew} />

        <div className="prompt-detail-column">
          <PromptEditorPanel
            draft={state.draft} detail={detail} mode={mode}
            locked={controller.locked || !writable} busy={state.loading}
            canSave={controller.canSave && writable}
            conflictCode={state.conflictCode} saveError={state.error}
            fieldError={state.fieldError}
            onEdit={edit} onSave={save} onRetry={retry}
            onRebase={() => { if (detail) void rebase(detail.familyId); }} onDiscard={discard} />

          {detail && (
            <section className="prompt-history" aria-label="版本历史">
              <h3>版本历史</h3>
              {!detail.historyComplete && (
                <StatusMessage tone="warning">
                  这个家族的修订链**不完整**（有删除、缺失或重复的修订）。
                  下面显示的不是一段可信的完整历史，请不要把某一版当作权威最新版。
                </StatusMessage>
              )}
              <ol className="prompt-version-list">
                {[...versions].sort((a, b) => b.revision - a.revision).map(row => (
                  <li key={row.assetId}>
                    <span>修订 {row.revision}</span>
                    {row.assetId === detail.headAssetId && <Badge tone="info">当前</Badge>}
                    {!row.available && <Badge tone="warning">已删除 / 不可读</Badge>}
                    {row.redacted && <Badge tone="warning">已脱敏</Badge>}
                    {row.changeNote && <span className="prompt-version-note">{row.changeNote}</span>}
                    {mode === 'PROFESSIONAL' && <code>{row.assetId.slice(0, 8)}</code>}
                  </li>
                ))}
              </ol>
              {detail.anomalies.length > 0 && (
                <ul className="prompt-anomalies">
                  {detail.anomalies.map(row => <li key={row.kind}>{row.kind} {row.detail}</li>)}
                </ul>
              )}

              <h3>版本比较</h3>
              {versions.length < 2 ? (
                <p>至少需要两个修订才能比较。</p>
              ) : (
                <>
                  <div className="prompt-compare-picker">
                    <label htmlFor="prompt-from">对比旧版</label>
                    <select id="prompt-from" value={fromId} onChange={event => setFromId(event.target.value)}>
                      {versions.map(row => (
                        <option key={row.assetId} value={row.assetId}>
                          修订 {row.revision}{row.available ? '' : '（不可读）'}
                        </option>
                      ))}
                    </select>
                    <label htmlFor="prompt-to">与新版</label>
                    <select id="prompt-to" value={toId} onChange={event => setToId(event.target.value)}>
                      {versions.map(row => (
                        <option key={row.assetId} value={row.assetId}>修订 {row.revision}</option>
                      ))}
                    </select>
                    <Button disabled={!fromId || !toId || comparison.loading}
                      onClick={() => {
                        const masked = versions.filter(
                          row => row.redacted && (row.assetId === fromId || row.assetId === toId));
                        if (masked.length > 0) {
                          // Refuse by default; this is not an unlock feature and needs no
                          // new permission system. The authorised raw read still exists
                          // outside this panel.
                          setMaskNotice('选中的修订包含已标记为「展示遮罩」的版本'
                            + `（修订 ${masked.map(row => row.revision).join('、')}），`
                            + '默认不参与明文比较。请改选未遮罩的修订。');
                          return;
                        }
                        setMaskNotice(null);
                        void compare(detail.familyId, fromId, toId);
                      }}>
                      {comparison.loading ? '正在读取正文…' : '比较正文'}
                    </Button>
                  </div>
                  {maskNotice && <StatusMessage tone="warning">{maskNotice}</StatusMessage>}
                  {comparison.error && <StatusMessage tone="error">{comparison.error}</StatusMessage>}
                  {comparison.from && comparison.to && (
                    <RevisionDiff
                      from={comparison.from} to={comparison.to} professional={mode === 'PROFESSIONAL'} />
                  )}
                </>
              )}
            </section>
          )}
        </div>
      </div>
    </Panel>
  );
}

export { RevisionDiff } from './PromptRevisionDiff';

export { needsRebase };
