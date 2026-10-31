import type {CanvasTaskAdoption} from './canvasTaskBinding';

export function sameCanvasAdoptionTarget(currentTaskId: string, current: CanvasTaskAdoption | undefined,
  historicTaskId: string, historic: CanvasTaskAdoption): boolean {
  return currentTaskId === historicTaskId && !!current
    && (['assetId', 'assetVersion', 'assetSha256', 'jobObservationSha256'] as const).every(key => current[key] === historic[key]);
}

/** Compare browser records only. These labels make no current server/permission claim. */
export function canvasAdoptionHistoryDifferences(currentTaskId: string, current: CanvasTaskAdoption | undefined,
  historicTaskId: string, historic: CanvasTaskAdoption): string[] {
  const differences: string[] = [];
  if (currentTaskId !== historicTaskId) differences.push('原任务 ID 不同');
  if (!current) return [...differences, '当前记录没有采用资产'];
  if (current.assetId !== historic.assetId) differences.push('资产 ID 不同');
  if (current.assetVersion !== historic.assetVersion) differences.push('读取时资产版本不同');
  if (current.assetSha256 !== historic.assetSha256) differences.push('图片内容摘要不同');
  if (current.jobObservationSha256 !== historic.jobObservationSha256) differences.push('原任务观察摘要不同');
  return differences.length ? differences : ['上述本机记录字段相同，仍未重新核验'];
}
