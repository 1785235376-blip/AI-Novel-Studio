import { useCallback, useMemo, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createDirectorWorkspaceClient } from '../director/directorWorkspaceClient';
import { DirectorWorkspace } from '../director/DirectorWorkspace';
import { createBibleClient } from '../bible/bibleClient';
import { BibleWorkspace } from '../bible/BibleWorkspace';
import { createStoryboardWorkspaceClient } from './storyboardWorkspaceClient';
import { directorVsShotOverride } from './storyboardOps';
import { DirectorGoalPanel } from './DirectorGoalPanel';
import { ShotDetailPanel } from './ShotDetailPanel';
import { PromptAdoptionDisclosure } from './PromptAdoptionDisclosure';
import { PromptAdoptionWritePanel } from './PromptAdoptionWritePanel';
import { ShotList } from './ShotList';
import { ShotSendToPanel } from './ShotSendToPanel';
import { useStoryboardWorkspace } from './useStoryboardWorkspace';
import type { BoundShotTargetDraft, DirectorGoalDraft, SendTarget } from './storyboardWorkspaceTypes';
import type { CreativeDocument } from '../creative/types';
import './storyboardWorkspace.css';

/** 冻结的挂载契约。父级只通过它把身份、闸门与回调注入进来。 */
export type StoryboardWorkspacePanelProps = {
  projectId: string;
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
  identity: string;
  active: boolean;
  denied: boolean;
  busy: boolean;
  /** Only the original host may admit writes. Missing remains read-only. */
  writable?: boolean;
  /** Verified original document, returned to the host's existing clean document state. */
  onDocumentCommitted?: (document: CreativeDocument, expectedTargetVersion: number) => void;
  isCurrent: () => boolean;
  read: <T>(w: () => Promise<T>) => Promise<T>;
  mutate: <T>(w: () => Promise<T>) => Promise<T>;
  selectedShotId?: string;
  onSelectShot?: (shotId: string) => void;
  /**
   * Phase14-A：导演工作台默认读取本面板正在看的那份文档。父级可以显式指定另一份；
   * 不给也不会猜——读不到文档标识时工作台保持"尚未选定文档"，不发请求。
   */
  directorDocumentId?: string;
  onSendTo?: (target: 'IMAGE' | 'VIDEO' | 'TIMELINE', draft: {
    shot_id: string; shot_version: number; document_version: number; source_digest: string;
  }) => void;
  onUnavailable?: () => void;
};

const segment = encodeURIComponent;

/**
 * 分镜工作区面板：组合 + 挂载入口。
 *
 * 它读到的每个字节都来自注入的传输，并且都经过父级的 `read` 闸门；没有定时器，
 * 显示顺序草稿留在本地；Prompt 采用仅经显式开放的原写入口。跨模块动作只通过
 * `onSendTo` 回调交回调用方 —— 本组件自己**不**导航、不执行。
 */
export function StoryboardWorkspacePanel(props: StoryboardWorkspacePanelProps) {
  const client = useMemo(
    () => createStoryboardWorkspaceClient(props.projectId, props.transport, props.scope),
    [props.projectId, props.transport, props.scope],
  );
  // 导演文档与待审建议是次要读取；它们的端口来自既有 creative 客户端，不新造接口。
  const creativeBase = `/api/novels/${segment(props.projectId)}/experimental/creative`;
  const getDocument = useCallback((documentId: string, signal?: AbortSignal) =>
    props.transport.json<CreativeDocument>(`${creativeBase}/documents/${segment(documentId)}`, 'GET', undefined, signal),
  [creativeBase, props.transport]);
  const listProposals = useCallback((signal?: AbortSignal) =>
    props.transport.json<{ items: unknown[] }>(`${creativeBase}/director-proposals`, 'GET', undefined, signal),
  [creativeBase, props.transport]);

  const [draft, setDraft] = useState<BoundShotTargetDraft | null>(null);
  const [comparison, setComparison] = useState<{ kind: 'IMAGE' | 'VIDEO'; asset_id: string; version: number; digest: string; matches_version: boolean } | null>(null);
  const [goalNotice, setGoalNotice] = useState('');
  const [directorOpen, setDirectorOpen] = useState(false);
  const [bibleOpen, setBibleOpen] = useState(false);
  const [adoptionRefresh, setAdoptionRefresh] = useState(0);
  const directorClient = useMemo(
    () => createDirectorWorkspaceClient(props.projectId, props.transport, props.scope),
    [props.projectId, props.transport, props.scope],
  );
  // 角色与场景圣经是项目级的，不需要文档标识。
  const bibleClient = useMemo(
    () => createBibleClient(props.projectId, props.transport, props.scope),
    [props.projectId, props.transport, props.scope],
  );

  const controller = useStoryboardWorkspace({
    identity: props.identity, active: props.active, denied: props.denied, busy: props.busy,
    isCurrent: props.isCurrent, read: props.read, client,
    getDocument, listProposals,
    onUnavailable: props.onUnavailable,
  });

  const prepare = (target: SendTarget) => {
    const next = controller.prepareDraft(target);
    setDraft(next);
    return next;
  };

  const compare = () => {
    const row = controller.selected;
    if (!row) return;
    const candidate = row.summary.candidate;
    if (!candidate) { setComparison(null); controller.toast('这个镜头还没有可比较的正式绑定素材。'); return; }
    setComparison({
      kind: candidate.kind, asset_id: candidate.ref.asset_id, version: candidate.ref.version,
      digest: candidate.ref.digest,
      matches_version: candidate.kind === 'IMAGE'
        ? row.shot.image_asset !== null
        : !!row.shot.video_result && row.shot.video_result.source_shot.shot_version === row.shot.shot_version,
    });
  };

  const resolution = useMemo(
    () => (controller.selectedGoal && controller.selectedShot
      ? directorVsShotOverride(controller.selectedGoal, controller.selectedShot) : null),
    [controller.selectedGoal, controller.selectedShot],
  );

  if (!props.active) {
    return <section className="storyboard-workspace" aria-label="分镜工作区" data-active="false" />;
  }

  return <section className="storyboard-workspace" aria-label="分镜工作区" data-active="true">
    <div className="storyboard-workspace__bar">
      <h2>导演与分镜</h2>
      <Badge tone="neutral">项目 {props.projectId}</Badge>
      <Badge tone="neutral">文档 {controller.receipt?.document_snapshot.id ?? '尚未读取'}</Badge>
      <Badge tone={controller.receipt?.approved ? 'success' : 'warning'}>
        {controller.receipt ? (controller.receipt.approved ? '原分镜已批准' : '等待原分镜审核') : '尚未读取批准状态'}
      </Badge>
      <Button disabled={controller.locked} onClick={() => void controller.load()}>读取已保存分镜</Button>
      <Button disabled={controller.loading} onClick={() => void controller.load()}>重新读取</Button>
    </div>
    {props.denied && <StatusMessage tone="warning">当前会话被拒绝读取这份分镜（DENIED）。请核对身份与项目范围。</StatusMessage>}
    {controller.problem && <StatusMessage tone="error">{controller.problem.code}：{controller.problem.message}</StatusMessage>}
    {controller.notice && <StatusMessage tone="info">{controller.notice}</StatusMessage>}

    <div className="storyboard-workspace__body">
      <ShotList
        rows={controller.rows}
        selectedShotId={controller.selectedShotId}
        onSelect={shotId => { controller.chooseShot(shotId); props.onSelectShot?.(shotId); }}
        onReorder={controller.reorder}
        orderSaved={controller.orderDraft?.saved ?? true}
        renumbered={controller.orderDraft?.renumbered ?? []}
        state={controller.state}
        problem={controller.problem}
        loading={controller.loading}
        canRead={controller.canRead}
        onRead={() => void controller.load()}
        onResetOrder={controller.resetOrder}
      />
      <div className="storyboard-workspace__detail">
        <ShotDetailPanel
          row={controller.selected}
          neighbours={controller.neighboursOf}
          onCompare={compare}
          onPrepareDraft={prepare}
          comparison={comparison}
          resolution={resolution}
          locked={controller.locked}
        />
        {/* R3-I: read-only adoption provenance, COLLAPSED BY DEFAULT so nothing is fetched until
            the user asks. It reuses this panel's own transport and read gate. The target document
            is the STORYBOARD document: directorDocumentId can point at a DIFFERENT director
            document, so it must not be used here or the projection would be requested for the
            wrong document. GET only: no POST and no write affordance while the switch is closed. */}
        <PromptAdoptionDisclosure
          projectId={props.projectId}
          documentId={controller.receipt?.document_snapshot.id ?? null}
          identity={`${props.identity}|adoption:${adoptionRefresh}`}
          read={props.read}
          shotId={controller.selected?.summary.shot_id ?? null}
          transport={props.transport}
          enabled={props.active && !props.denied && props.isCurrent()}
        />
        <PromptAdoptionWritePanel
          projectId={props.projectId} identity={props.identity} transport={props.transport}
          target={controller.receipt && controller.selected ? {
            documentId: controller.receipt.document_snapshot.id,
            shotId: controller.selected.summary.shot_id,
            version: controller.receipt.document_snapshot.version,
            digest: controller.receipt.document_snapshot.digest,
          } : null}
          enabled={props.active && !props.denied && props.isCurrent()} busy={props.busy || controller.loading}
          writable={props.writable === true}
          isCurrent={props.isCurrent} read={props.read} mutate={props.mutate} readDocument={getDocument}
          onUnavailable={props.onUnavailable}
          onCommitted={async (document, expectedTargetVersion) => {
            if (!props.isCurrent()) throw new Error('工作区身份或草稿已变化。');
            props.onDocumentCommitted?.(document, expectedTargetVersion);
            await controller.load();
            if (!props.isCurrent()) throw new Error('工作区身份或草稿已变化。');
            setAdoptionRefresh(value => value + 1);
            controller.toast('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。');
          }}
        />
        <ShotSendToPanel
          row={controller.selected}
          draft={draft}
          locked={controller.locked}
          orderShotIds={draft?.order_shot_ids ?? []}
          onPrepare={prepare}
          onSend={(target, value) => {
            if (typeof value.document_version !== 'number') return;
            props.onSendTo?.(target, {
              shot_id: value.shot_id, shot_version: value.shot_version,
              document_version: value.document_version, source_digest: value.source_digest,
            });
            controller.toast('草稿已交给调用方；本工作区没有执行任何目标模块，也没有离开当前位置。');
          }}
          onUnavailable={props.onUnavailable}
        />
        <DirectorGoalPanel
          goals={controller.goals}
          selectedGoal={controller.selectedGoal}
          shot={controller.selectedShot}
          visualTarget={controller.visualTarget}
          proposals={controller.proposals}
          locked={controller.locked}
          notice={goalNotice}
          onCommit={(value: DirectorGoalDraft) => setGoalNotice(
            `已形成目标草稿（本地）：${value.note_id}。原导演文档没有被写入，也没有自动覆盖已批准的下游结果。`)}
          onDiscard={() => setGoalNotice('已放弃这条本地草稿，原文档未变。')}
          onReadAdvice={() => setGoalNotice('导演调度建议是只读的：它不会自动应用，也不会调用模型。')}
        />
        {controller.document && <Panel title="上游导演文档（只读）">
          <p>{controller.document.title} · v{controller.document.version} · {controller.document.mode}</p>
          <p>导演是可选的创作节点：这里是只读引用，不会因此获得对其它模块的核心权威。</p>
        </Panel>}
        <div className="director-workspace__entry">
          <Button onClick={() => setDirectorOpen(true)} aria-expanded={directorOpen}>
            按需打开导演工作台
          </Button>
          {directorOpen && <DirectorWorkspace
            client={directorClient}
            documentId={props.directorDocumentId ?? controller.receipt?.document_snapshot.id ?? null}
            active={props.active}
          />}
          <Button onClick={() => setBibleOpen(true)} aria-expanded={bibleOpen}>
            按需打开角色与场景圣经
          </Button>
          {bibleOpen && <BibleWorkspace client={bibleClient} active={props.active} />}
        </div>
      </div>
    </div>
  </section>;
}
