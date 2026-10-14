/**
 * Phase14-A 控制器。
 *
 * 只负责"读一次、如实呈现"：没有写入、没有乐观更新、没有本地修改原文档的路径。
 * 状态集合与其它工作区一致（IDLE/LOADING/READY/EMPTY/DENIED/FAILED），
 * 失败一律保留机器码，不把失败吞成空数据。
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '../api';
import type {
  DirectorWorkspaceClient, DirectorWorkspaceProblem, DirectorWorkspaceProjection,
  DirectorWorkspaceSurfaceState,
} from './directorWorkspaceTypes';

export type DirectorWorkspaceController = {
  state: DirectorWorkspaceSurfaceState;
  problem: DirectorWorkspaceProblem | null;
  projection: DirectorWorkspaceProjection | null;
  read: (documentId: string) => Promise<void>;
  reset: () => void;
};

function problemOf(reason: unknown): DirectorWorkspaceProblem {
  if (reason instanceof ApiError) return { code: reason.problem.code, message: reason.problem.message };
  return { code: 'STUDIO_DIRECTOR_WORKSPACE_READ_FAILED', message: reason instanceof Error ? reason.message : String(reason) };
}

/** 一份"什么都没写"的文档：没有镜头，也没有任何文档级意图。 */
function isEmpty(projection: DirectorWorkspaceProjection): boolean {
  const authored = projection.director_intent.fields.some(field => field.authored)
    || projection.director_intent.fields.some(field => field.usage !== null && field.usage.measured_over_rows > 0);
  return projection.shot_cards.length === 0 && !authored;
}

export function useDirectorWorkspace(client: DirectorWorkspaceClient | null): DirectorWorkspaceController {
  const [state, setState] = useState<DirectorWorkspaceSurfaceState>('IDLE');
  const [problem, setProblem] = useState<DirectorWorkspaceProblem | null>(null);
  const [projection, setProjection] = useState<DirectorWorkspaceProjection | null>(null);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => () => pending.current?.abort(), []);

  const reset = useCallback(() => {
    pending.current?.abort();
    pending.current = null;
    setState('IDLE');
    setProblem(null);
    setProjection(null);
  }, []);

  const read = useCallback(async (documentId: string) => {
    if (!client) {
      setState('FAILED');
      setProblem({ code: 'STUDIO_DIRECTOR_WORKSPACE_READ_FAILED', message: '导演工作台尚未连接到原 owner 的读取通道。' });
      return;
    }
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setState('LOADING');
    setProblem(null);
    try {
      const result = await client.readDirectorWorkspace(documentId, controller.signal);
      if (controller.signal.aborted) return;
      setProjection(result);
      setState(isEmpty(result) ? 'EMPTY' : 'READY');
    } catch (reason) {
      if (controller.signal.aborted) return;
      const failure = problemOf(reason);
      setProjection(null);
      setProblem(failure);
      setState(reason instanceof ApiError && reason.problem.status === 403 ? 'DENIED' : 'FAILED');
    }
  }, [client]);

  return { state, problem, projection, read, reset };
}
