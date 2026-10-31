/**
 * Round2-B 控制器：读一次，如实呈现。
 *
 * 没有写入、没有乐观更新、没有编辑草稿：本工作面是本轮唯一**纯只读**的 Studio 面板。
 * 状态集合与其它工作区一致（IDLE/LOADING/READY/EMPTY/DENIED/FAILED），失败保留机器码，
 * 绝不把失败吞成"暂无内容"。
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '../api';
import type { BibleClient, BibleProblem, BibleProjection, BibleSurfaceState } from './bibleTypes';

export type BibleController = {
  state: BibleSurfaceState;
  problem: BibleProblem | null;
  projection: BibleProjection | null;
  read: () => Promise<void>;
  reset: () => void;
};

function problemOf(reason: unknown): BibleProblem {
  if (reason instanceof ApiError) return { code: reason.problem.code, message: reason.problem.message };
  return { code: 'STUDIO_BIBLE_READ_FAILED', message: reason instanceof Error ? reason.message : String(reason) };
}

/** 项目还没有任何角色、地点或世界记录。 */
function isEmpty(projection: BibleProjection): boolean {
  return projection.character_bible.entries.length === 0 && projection.scene_bible.entries.length === 0;
}

export function useBible(client: BibleClient | null): BibleController {
  const [state, setState] = useState<BibleSurfaceState>('IDLE');
  const [problem, setProblem] = useState<BibleProblem | null>(null);
  const [projection, setProjection] = useState<BibleProjection | null>(null);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => () => pending.current?.abort(), []);

  const reset = useCallback(() => {
    pending.current?.abort();
    pending.current = null;
    setState('IDLE');
    setProblem(null);
    setProjection(null);
  }, []);

  const read = useCallback(async () => {
    if (!client) {
      setState('FAILED');
      setProblem({ code: 'STUDIO_BIBLE_READ_FAILED', message: '角色与场景圣经尚未连接到原 owner 的读取通道。' });
      return;
    }
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setState('LOADING');
    setProblem(null);
    try {
      const result = await client.readBible(controller.signal);
      if (controller.signal.aborted) return;
      setProjection(result);
      setState(isEmpty(result) ? 'EMPTY' : 'READY');
    } catch (reason) {
      if (controller.signal.aborted) return;
      setProblem(problemOf(reason));
      setProjection(null);
      setState(reason instanceof ApiError && reason.problem.status === 403 ? 'DENIED' : 'FAILED');
    }
  }, [client]);

  return { state, problem, projection, read, reset };
}
