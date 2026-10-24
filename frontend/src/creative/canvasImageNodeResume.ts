import { ApiError } from '../api';
import { exactStudioProductionTask, type StudioProductionTask } from '../taskcenter/studioProductionTask';
import { assertCanvasImageNodeJob, canvasImageNodeInCommand, canonicalImageNode, verifyCanvasImageNodePrompt,
  type CanvasImageNodeBinding } from './canvasImageNode';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioClient } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';

/** An ephemeral original-owner handoff. It is never written to a browser graph or hint. */
export type CanvasImageNodeResume = { job: StudioProductionTask; canvas: CanvasViewRecord;
  binding: CanvasImageNodeBinding; initialPrompt: string; canReview: boolean; readOnly: boolean };
export type CanvasImageNodeResumeInput = { selected: StudioProductionTask; projectId: string; branchId: string | null;
  client: Pick<StudioClient, 'overview' | 'graphs'>;
  production: Pick<StudioProductionClient, 'get' | 'resolveImageNodeCreate'>;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>; signal?: AbortSignal;
  readOnly?: boolean };

function invalid(message: string): never {
  throw new ApiError({ status: 409, code: 'STUDIO_CANVAS_NODE_RESUME_CHANGED', message });
}

/** Read the exact selected Job and original Canvas, without granting an action. */
export async function prepareCanvasImageNodeResume(input: CanvasImageNodeResumeInput): Promise<CanvasImageNodeResume> {
  const selected = structuredClone(input.selected), controller = new AbortController(), readOnly = input.readOnly === true;
  const aborted = () => controller.abort();
  input.signal?.addEventListener('abort', aborted, { once: true });
  if (input.signal?.aborted) controller.abort();
  const current = () => {
    if (controller.signal.aborted) throw new DOMException('节点任务续接读取已取消。', 'AbortError');
    if (!input.isCurrent()) invalid('原任务选择、项目或身份已改变，未续接其他位置。');
  };
  const read = async <T,>(work: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    current();
    const result = await input.read(() => { current(); return work(controller.signal); }, controller.signal);
    current(); return result;
  };
  let timer: ReturnType<typeof setTimeout> | undefined;
  let rejectAborted: (() => void) | undefined;
  const cancelled = new Promise<never>((_resolve, reject) => {
    rejectAborted = () => reject(new DOMException('节点任务续接读取已取消。', 'AbortError'));
    controller.signal.addEventListener('abort', rejectAborted, { once: true });
    if (controller.signal.aborted) rejectAborted();
  });
  const timeout = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => { reject(new Error('原节点任务读取超时，未开启续接；请重新选择原任务。')); controller.abort(); }, 15_000);
  });
  try {
    return await Promise.race([(async () => {
      current();
      const binding = canvasImageNodeInCommand(selected.command);
      const supportedStatus = readOnly ? ['RUNNING', 'UNKNOWN', 'CANCELLED'].includes(selected.status) : selected.status === 'QUEUED';
      if (!binding || !supportedStatus || selected.owner !== 'image'
        || selected.novel_id !== input.projectId || selected.branch_id !== input.branchId
        || binding.project_id !== input.projectId
        || (binding.scope.mode === 'collaboration' ? binding.scope.branch_id : null) !== input.branchId)
        invalid('此入口仅续接当前项目明确选中的排队任务，或只读的运行中、未知与已取消图片节点任务。');
      assertCanvasImageNodeJob(binding, selected);
      await verifyCanvasImageNodePrompt(selected.command!); current();
      const resolver = input.production.resolveImageNodeCreate;
      if (!resolver || !input.client.graphs.canvasViews) invalid('当前服务缺少精确原任务或画布读取能力，未开启续接。');
      const overview = await read(signal => input.client.overview(signal));
      if (overview.project.id !== input.projectId || overview.project.incarnation !== binding.incarnation
        || !readOnly && overview.capabilities.can_mutate !== true)
        invalid(readOnly ? '原项目或代次未确认，未开启只读任务续接。' : '原项目代次或当前写入能力未确认，未开启任务续接。');
      const resolved = await read(signal => resolver(selected.request_id, selected.request_digest, binding, signal));
      exactStudioProductionTask(resolved, selected, input.projectId, input.branchId);
      assertCanvasImageNodeJob(binding, resolved);
      const canvas = await read(signal => input.client.graphs.canvasViews!.get(binding.canvas_id, signal));
      const history = await read(signal => input.client.graphs.canvasViews!.history(binding.canvas_id, signal));
      if (canvas.id !== binding.canvas_id || canvas.project_id !== input.projectId
        || canonicalImageNode(canvas.scope) !== canonicalImageNode(binding.scope)
        || canvas.version !== binding.canvas_version || canvas.definition_digest !== binding.canvas_digest
        || canvas.definition.cards.length !== 0 || canvas.definition.image_node_origin
        || history.id !== canvas.id || history.project_id !== input.projectId
        || canonicalImageNode(history.scope) !== canonicalImageNode(binding.scope)
        || history.incarnation !== binding.incarnation || history.current_version !== canvas.version
        || history.current_definition_digest !== canvas.definition_digest)
        invalid('原节点画布、范围、代次或版本已改变，未改选其他作品位置。');
      const latest = await read(signal => input.production.get('image', selected.id, signal));
      const exact = exactStudioProductionTask(latest, selected, input.projectId, input.branchId);
      assertCanvasImageNodeJob(binding, exact); current();
      return { job: exact, canvas, binding: structuredClone(binding), initialPrompt: exact.command!.prompt,
        canReview: !readOnly && overview.capabilities.can_review === true, readOnly };
    })(), timeout, cancelled]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
    if (rejectAborted) controller.signal.removeEventListener('abort', rejectAborted);
    controller.abort(); input.signal?.removeEventListener('abort', aborted);
  }
}
