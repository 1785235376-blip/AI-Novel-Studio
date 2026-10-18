import { useMemo, useState } from 'react';
import { StudioComicImageGeneration } from './StudioComicImageGeneration';
import { studioComicImageClient } from './studioComicImageClient';
import { studioProductionClient } from './studioProductionClient';
import { ApiError, type CollaborationContext } from '../api';
import { ComicLayoutsPanel } from '../experimental/ComicLayoutsPanel';
import type { ExperimentalClient } from '../experimental/api';
import { StatusMessage } from '../ui/primitives';
import { studioTransport } from './studioClient';
import type { BlobReadLimit } from '../boundedResponseBlob';

/** Image subview over the original B06 owner; no copied documents or permission fallback. */
export function StudioComicPanel({ projectId, context, isCurrent, onDirtyChange, onBusyChange, canMutate = false, canReview = false }: {
  canMutate?: boolean; canReview?: boolean; projectId: string; context: CollaborationContext; isCurrent: () => boolean;
  onDirtyChange: (dirty: boolean) => void; onBusyChange: (busy: boolean) => void;
}) {
  const production = useMemo(() => studioProductionClient(projectId, context), [projectId, context]);
  const imageClient = useMemo(() => studioComicImageClient(projectId, context), [projectId, context]);
  const [denied, setDenied] = useState(false);
  const client = useMemo<ExperimentalClient>(() => {
    const transport = studioTransport(context);
    const root = `/api/novels/${encodeURIComponent(projectId)}/experimental`;
    const read = async <T,>(operation: () => Promise<T>): Promise<T> => {
      if (!isCurrent()) throw new ApiError({ status: 403, code: 'COMIC_AUTHORITY_CHANGED', message: '当前身份已变化，请重新打开漫画。' });
      try {
        const value = await operation();
        if (!isCurrent()) throw new ApiError({ status: 403, code: 'COMIC_AUTHORITY_CHANGED', message: '当前身份已变化，请重新打开漫画。' });
        return value;
      } catch (error) {
        if (isCurrent() && error instanceof ApiError && [401, 403].includes(error.status)) setDenied(true);
        throw error;
      }
    };
    return {
      get: <T,>(path: string, signal?: AbortSignal) => read(() => transport.json<T>(root + path, 'GET', undefined, signal)),
      post: <T,>(path: string, body: unknown) => read(() => transport.json<T>(root + path, 'POST', body)),
      postBlob: (path: string, body: unknown, limit?: BlobReadLimit) => read(() => transport.blobResponse(root + path, 'POST', body, undefined, undefined, limit)),
      put: <T,>(path: string, body: unknown) => read(() => transport.json<T>(root + path, 'PUT', body)),
      blob: (path: string, signal?: AbortSignal) => read(() => transport.blob(root + path, 'GET', undefined, signal)),
    };
  }, [projectId, context, isCurrent]);
  if (denied) return <StatusMessage tone="error">当前身份或分支没有漫画访问权限。图片模块导航不会授予权限；请核对原项目授权后重新打开。</StatusMessage>;
  return <><p>漫画制作沿用原项目与漫画记录。此入口仍需已启用的漫画、资产来源和导演能力，以及原项目授权；不会自动启用功能或调用模型。</p>
    <ComicLayoutsPanel renderImageGeneration={host => <StudioComicImageGeneration {...host} client={imageClient} production={production} canMutate={canMutate} canReview={canReview} />} client={client} isOwnerCurrent={isCurrent} onDirtyChange={onDirtyChange} onBusyChange={onBusyChange} /></>;
}
