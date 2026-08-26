import {useEffect, useState} from 'react';
import {AlertTriangle, Check, Clock3, RotateCcw} from 'lucide-react';
import {Badge, Button, EmptyState, Panel} from './ui/primitives';
import {revisionReasonLabel} from './productLanguage';
import './revision.css';

export interface RevisionSummary {
  version: number;
  createdAt: string;
  actorLabel: string;
  reason?: string;
  source?: string;
}

export interface RevisionComparison {
  historicalLabel: string;
  historicalText: string;
  currentLabel: string;
  currentText: string;
}

export interface RevisionDetail extends RevisionSummary {
  comparison: RevisionComparison;
}

export interface RevisionRestoreRequest {
  revisionVersion: number;
  expectedCurrentVersion: number;
}

export interface RevisionRestoreFailure {
  kind: 'conflict' | 'unauthorized' | 'error';
  message: string;
  currentVersion?: number;
}

export interface RevisionPanelProps {
  revisions: RevisionSummary[];
  currentVersion: number;
  selectedRevision?: RevisionDetail | null;
  loading?: boolean;
  detailLoading?: boolean;
  error?: string | null;
  detailError?: string | null;
  unauthorized?: boolean;
  onSelectRevision: (version: number) => void;
  onRestore: (request: RevisionRestoreRequest) => Promise<void>;
}

function failureFrom(reason: unknown): RevisionRestoreFailure {
  if (reason && typeof reason === 'object' && 'kind' in reason && 'message' in reason) {
    const candidate = reason as RevisionRestoreFailure;
    if (['conflict', 'unauthorized', 'error'].includes(candidate.kind)) return candidate;
  }
  return {kind: 'error', message: reason instanceof Error ? reason.message : '恢复失败，请稍后重试。'};
}

function formatTime(value: string) {
  const time = new Date(value);
  return Number.isNaN(time.valueOf()) ? value : time.toLocaleString();
}
function reasonLabel(value?: string) {
  if (!value) return '系统保存';
  const label = revisionReasonLabel(value);
  return label === value && /^[A-Z_]+$/.test(value) ? '系统保存' : label;
}
function actorLabel(value: string) {
  return !value || /^acceptance-|^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value) ? '协作者' : value;
}

export function RevisionPanel({
  revisions,
  currentVersion,
  selectedRevision,
  loading = false,
  detailLoading = false,
  error,
  detailError,
  unauthorized = false,
  onSelectRevision,
  onRestore,
}: RevisionPanelProps) {
  const [confirming, setConfirming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreFailure, setRestoreFailure] = useState<RevisionRestoreFailure>();
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    setConfirming(false);
    setRestoreFailure(undefined);
    setRestored(false);
  }, [selectedRevision?.version]);

  async function confirmRestore() {
    if (!selectedRevision || restoring) return;
    setRestoring(true);
    setRestored(false);
    try {
      await onRestore({
        revisionVersion: selectedRevision.version,
        expectedCurrentVersion: currentVersion,
      });
      setConfirming(false);
      setRestoreFailure(undefined);
      setRestored(true);
    } catch (reason) {
      setRestoreFailure(failureFrom(reason));
    } finally {
      setRestoring(false);
    }
  }

  if (unauthorized) {
    return <Panel title="版本记录" className="revision-panel"><div className="revision-state revision-state--error" role="alert"><AlertTriangle aria-hidden="true"/><div><strong>无权查看版本记录</strong><p>请联系创作空间管理员获取访问权限。</p></div></div></Panel>;
  }
  if (loading) {
    return <Panel title="版本记录" className="revision-panel"><div className="revision-state" role="status" aria-live="polite"><Clock3 aria-hidden="true"/>正在加载版本记录…</div></Panel>;
  }
  if (error) {
    return <Panel title="版本记录" className="revision-panel"><div className="revision-state revision-state--error" role="alert"><AlertTriangle aria-hidden="true"/><div><strong>无法加载版本记录</strong><p>{error}</p></div></div></Panel>;
  }

  return (
    <Panel title="版本记录" className="revision-panel">
      {!revisions.length ? <EmptyState title="暂无历史版本" detail="保存内容后，历史版本会显示在这里。"/> : (
        <div className="revision-layout">
          <nav className="revision-timeline" aria-label="版本记录时间线">
            <ol>
              {revisions.map(revision => {
                const selected = selectedRevision?.version === revision.version;
                return <li key={revision.version}>
                  <button type="button" className={selected ? 'is-selected' : ''} aria-current={selected ? 'true' : undefined} onClick={() => onSelectRevision(revision.version)}>
                    <span className="revision-timeline__heading"><strong>版本 {revision.version}</strong>{revision.version === currentVersion && <Badge tone="success">当前</Badge>}</span>
                    <span>{reasonLabel(revision.reason || revision.source)}</span>
                    <small>{actorLabel(revision.actorLabel)} · {formatTime(revision.createdAt)}</small>
                  </button>
                </li>;
              })}
            </ol>
          </nav>

          <section className="revision-detail" aria-label="版本详情" aria-busy={detailLoading}>
            {detailLoading && <div className="revision-state" role="status" aria-live="polite"><Clock3 aria-hidden="true"/>正在加载版本详情…</div>}
            {!detailLoading && detailError && <div className="revision-state revision-state--error" role="alert"><AlertTriangle aria-hidden="true"/>{detailError}</div>}
            {!detailLoading && !detailError && !selectedRevision && <EmptyState title="选择一个历史版本" detail="查看它与当前内容的差异，并预览恢复结果。"/>}
            {!detailLoading && !detailError && selectedRevision && <>
              <header className="revision-detail__header">
                <div><h3>历史版本 {selectedRevision.version}</h3><p>{reasonLabel(selectedRevision.reason || selectedRevision.source)} · {actorLabel(selectedRevision.actorLabel)} · {formatTime(selectedRevision.createdAt)}</p></div>
                <Badge tone={selectedRevision.version === currentVersion ? 'success' : 'neutral'}>{selectedRevision.version === currentVersion ? '当前版本' : `当前版本 ${currentVersion}`}</Badge>
              </header>
              <div className="revision-comparison" aria-label={`历史版本 ${selectedRevision.version} 与当前版本 ${currentVersion} 的正文比较`}>
                <section><h4>{selectedRevision.comparison.historicalLabel}</h4><div className="revision-body">{selectedRevision.comparison.historicalText}</div></section>
                <section><h4>{selectedRevision.comparison.currentLabel}</h4><div className="revision-body">{selectedRevision.comparison.currentText}</div></section>
              </div>

              {restoreFailure && <div className="revision-state revision-state--error revision-restore-message" role="alert">
                <AlertTriangle aria-hidden="true"/><div><strong>{restoreFailure.kind === 'conflict' ? '版本冲突，未恢复' : restoreFailure.kind === 'unauthorized' ? '无权恢复此版本' : '恢复失败'}</strong><p>{restoreFailure.message}</p>{restoreFailure.currentVersion !== undefined && <p>当前版本：v{restoreFailure.currentVersion}</p>}</div>
              </div>}
              {restored && <div className="revision-state revision-state--success revision-restore-message" role="status"><Check aria-hidden="true"/>恢复完成，所选内容已成为新的当前版本。</div>}

              {selectedRevision.version === currentVersion ? <p className="revision-current-note">这是当前版本，无需恢复。</p> : confirming ? (
                <div className="revision-confirm" role="group" aria-label="确认恢复历史版本">
                  <p><strong>恢复历史版本 {selectedRevision.version}？</strong></p>
                  <p>恢复后会以这份正文创建一个新的当前版本；现有历史版本不会被删除。</p>
                  <div className="revision-actions">
                    <Button variant="primary" type="button" disabled={restoring} onClick={confirmRestore}>{restoring ? '正在恢复…' : '恢复此版本'}</Button>
                    <Button type="button" disabled={restoring} onClick={() => setConfirming(false)}>取消</Button>
                  </div>
                </div>
              ) : <Button type="button" onClick={() => setConfirming(true)}><RotateCcw aria-hidden="true"/>预览并恢复此版本</Button>}
            </>}
          </section>
        </div>
      )}
    </Panel>
  );
}
