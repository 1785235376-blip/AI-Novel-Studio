/**
 * [HERMIA-FE-20261022 X-UX-01] Shared honest empty / error / loading copy
 * for six workspaces + novel main path. Author language; 禁假绿空壳.
 */
import {useTz} from '../i18n';
import type {ReactNode} from 'react';
import {Button, EmptyState} from './primitives';
import './WorkspaceHonestEmpty.css';

export type HonestEmptyKind =
  | 'no_project'
  | 'no_chapter'
  | 'no_track'
  | 'load_failed'
  | 'loading'
  | 'empty_library'
  | 'empty_selection';

export type HonestWorkspace =
  | 'NOVEL' | 'IMAGE' | 'VIDEO' | 'AUDIO' | 'EDIT' | 'ASSETS';

const COPY: Record<HonestEmptyKind, {title: string; detail: (ws: HonestWorkspace) => string; cta?: string}> = {
  no_project: {
    title: '请先打开小说项目',
    detail: (ws) => ({
      NOVEL: '写作四象限需要一部已打开的书。打开或新建项目后再继续写。',
      IMAGE: '图片预览、参考与生成任务按小说项目隔离。打开项目后再进入图片工作区。',
      VIDEO: '视频三层（镜头脚本 / 画布 / 导演）需要绑定到一个小说项目。',
      AUDIO: '配音、音效与有声书清单需要绑定到一个小说项目。',
      EDIT: '剪辑多轨时间线需要绑定到一个小说/项目。NLE 不嵌入小说中区。',
      ASSETS: '资产库中的文件与引用关系按小说项目隔离。打开项目后再浏览。',
    }[ws]),
    cta: '打开项目',
  },
  no_chapter: {
    title: '尚未选择章节',
    detail: () => '写作主路径需要当前章节。从左侧章树点选一章，或新建章节后再继续写。',
    cta: '去选章节',
  },
  no_track: {
    title: '时间线上还没有可剪片段',
    detail: () => '本序列暂无轨道片段（只读演示壳可显示示例轨）。可从媒体池引用素材，或从「视频」显式送入后再剪。',
    cta: '打开媒体池',
  },
  load_failed: {
    title: '加载失败',
    detail: (ws) => `${labelOf(ws)}内容未能读出。可重试；不会自动重试，也不会假装已接通。`,
    cta: '重试',
  },
  loading: {
    title: '正在加载…',
    detail: (ws) => `正在读取${labelOf(ws)}真实状态，请稍候。`,
  },
  empty_library: {
    title: '库里还没有资产',
    detail: () => '当前项目资产库为空（诚实 0 条）。可导入文件，或到图片 / 声音 / 视频生成后再回来建立引用。此处不是生图台。',
    cta: '了解引用语义',
  },
  empty_selection: {
    title: '尚未选中内容',
    detail: (ws) => ({
      NOVEL: '点选一章或一条大纲，右栏会给出下一步。禁止空白属性板。',
      IMAGE: '暂无选中图片任务。可新建生成、加参考，或打开漫画子入口。',
      VIDEO: '暂无选中镜头。可在画布选节点、展开导演台，或显式送去剪辑。',
      AUDIO: '暂无选中声音任务。可新建配音 / 音效 / 有声书；成片请送去剪辑。',
      EDIT: '在时间线上点选片段以查看入出点。无选中时保留序列出口与导出下一步。',
      ASSETS: '未选中资产。可筛选库或导入；拖出到其它模块＝引用，不复制。',
    }[ws]),
  },
};

function labelOf(ws: HonestWorkspace): string {
  return {NOVEL: '小说', IMAGE: '图片', VIDEO: '视频', AUDIO: '声音', EDIT: '剪辑', ASSETS: '资产'}[ws];
}

export function honestEmptyCopy(kind: HonestEmptyKind, workspace: HonestWorkspace) {
  const row = COPY[kind];
  return {title: row.title, detail: row.detail(workspace), cta: row.cta};
}

/** Compact shared empty block — optional CTA button; never success/green tone. */
export function WorkspaceHonestEmpty({
  kind,
  workspace,
  onAction,
  actionLabel,
  extra,
}: {
  kind: HonestEmptyKind;
  workspace: HonestWorkspace;
  onAction?: () => void;
  actionLabel?: string;
  extra?: ReactNode;
}) {
  const tz = useTz(); // [HERMIA-FE-20261025 I18N P1] honest empty/error states — zh copy stays the source, translated at render
  const raw = honestEmptyCopy(kind, workspace);
  const title = tz(raw.title), detail = tz(raw.detail), cta = tz(raw.cta || '');
  const label = actionLabel ? tz(actionLabel) : cta;
  return (
    <div
      className="ws-honest-empty"
      role="status"
      data-honest-kind={kind}
      data-honest-workspace={workspace}
      data-capability-tone="neutral"
    >
      <EmptyState title={title} detail={detail} />
      {(onAction && label) ? (
        <Button type="button" onClick={onAction}>{label}</Button>
      ) : null}
      {extra}
      <small className="ws-honest-empty__mark">[HERMIA-FE-20261022 X-UX-01] {tz('诚实空态 · 禁假绿')}</small>
    </div>
  );
}
