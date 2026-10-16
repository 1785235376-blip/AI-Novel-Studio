import { useMemo, useState } from 'react';
import { ApiError } from '../api';
import { DirectorWorkspace } from '../director/DirectorWorkspace';
import type { DirectorWorkspaceClient } from '../director/directorWorkspaceTypes';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphClient } from './studioGraphClient';
import type { PlanningSnapshot } from './studioProductionGraphContract';

type Props = {
  client: Pick<StudioGraphClient, 'readDirectorWorkspace'>;
  nodeId: string;
  snapshot?: PlanningSnapshot;
  identity: string;
  active: boolean;
  referenceState?: 'CURRENT' | 'STALE' | 'UNAVAILABLE';
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
};

/** On-demand view of an existing Director participant, without a second owner. */
export function StudioGraphDirectorConsole(props: Props) {
  const { snapshot, referenceState } = props;
  if (!props.active || !props.isCurrent()) return null;
  if (!snapshot || referenceState === 'UNAVAILABLE') {
    return <StatusMessage tone="warning">导演来源当前不可读取，控制台已关闭。请重新核对图与来源权限。</StatusMessage>;
  }
  if (referenceState === 'STALE') {
    return <StatusMessage tone="warning">导演来源已变化，控制台未采用新版本。请在原文档与图中明确核对绑定。</StatusMessage>;
  }
  if (!props.client.readDirectorWorkspace) {
    return <StatusMessage>当前入口未连接导演控制台读取通道。</StatusMessage>;
  }
  // Replacing a node, source pin or authority unmounts both private output and
  // the existing workspace's local camera draft before another source can open.
  return <BoundDirectorConsole key={JSON.stringify([props.identity, props.nodeId, snapshot.id, snapshot.version, snapshot.digest])}
    {...props} snapshot={snapshot} />;
}

function BoundDirectorConsole({ client, snapshot, isCurrent, read }: Props & { snapshot: PlanningSnapshot }) {
  const [expanded, setExpanded] = useState(false);
  const boundClient = useMemo<DirectorWorkspaceClient>(() => ({
    async readDirectorWorkspace(documentId, signal) {
      const assertCurrent = () => {
        if (signal?.aborted) throw new DOMException('Read aborted', 'AbortError');
        if (!isCurrent() || documentId !== snapshot.id) {
          throw new ApiError({ status: 403, code: 'STUDIO_GRAPH_SCOPE_MISMATCH', message: '身份或项目范围已变化，导演控制台读取已关闭。' });
        }
      };
      assertCurrent();
      return read(async () => {
        assertCurrent();
        const result = await client.readDirectorWorkspace!(snapshot, signal);
        assertCurrent();
        if (result.document.id !== snapshot.id || result.document.version !== snapshot.version || result.document.mode !== 'DIRECTOR') {
          throw new ApiError({ status: 409, code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED', message: '导演来源与图中绑定不一致，未显示此结果。' });
        }
        return result;
      });
    },
  }), [client, snapshot.id, snapshot.version, snapshot.digest, isCurrent, read]);

  return <section aria-label="图节点导演控制台">
    <Button aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      {expanded ? '收起导演控制台' : '展开导演控制台并核对来源'}
    </Button>
    <p>控制台只读原导演意图与连续性提示。展开及刷新会核对绑定版本和摘要；连接、执行、审核仍由原图与任务服务处理。</p>
    {expanded && <DirectorWorkspace client={boundClient} documentId={snapshot.id} />}
  </section>;
}
