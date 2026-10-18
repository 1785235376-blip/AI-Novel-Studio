import type { CreativeInput } from './types';
export type StoryboardTimingMode = 'uniform' | 'total';
/** Pure authoring operation. Never changes numbering, continuity, bindings or media. */
export function previewStoryboardTiming(draft: CreativeInput, sceneId: string | undefined, mode: StoryboardTimingMode, input: string) {
  if (draft.mode !== 'STORYBOARD') throw new Error('请选择分镜草稿。');
  return previewAuthorTiming(draft, sceneId, mode, input);
}
export function previewDirectorTiming(draft: CreativeInput, sceneId: string | undefined, mode: StoryboardTimingMode, input: string) {
  if (draft.mode !== 'DIRECTOR') throw new Error('请选择导演草稿。');
  return previewAuthorTiming(draft, sceneId, mode, input);
}
function previewAuthorTiming(draft: CreativeInput, sceneId: string | undefined, mode: StoryboardTimingMode, input: string) {
  const items = draft.mode === 'DIRECTOR' ? draft.director_notes : draft.shots;
  if (!items.length || items.length > 200) throw new Error('请选择包含 1 至 200 个调度或镜头的草稿。');
  if (mode !== 'uniform' && mode !== 'total') throw new Error('时长分配方式无效。');
  if (!/^[1-9]\d{0,5}$/.test(input)) throw new Error('请填写正整数秒数。');
  const target = Number(input), ids = new Set(items.map(shot => shot.id));
  if (ids.size !== items.length || items.some(shot => !shot.id || !Number.isInteger(shot.duration_seconds) || shot.duration_seconds < 1 || shot.duration_seconds > 600)) throw new Error('请先修正重复身份或无效时长。');
  const selected = items.filter(shot => sceneId === undefined || shot.scene_id === sceneId);
  if (!selected.length) throw new Error('当前范围没有调度或镜头。');
  if (mode === 'uniform' && target > 600 || mode === 'total' && (target < selected.length || target > selected.length * 600)) throw new Error('每项须为 1 至 600 秒，目标总时长须落在所选范围内。');
  const before = selected.reduce((sum, shot) => sum + shot.duration_seconds, 0);
  // Reserve one second per shot, then share remaining seconds by existing duration.
  // Largest remainders use original authored order for deterministic ties.
  const assigned = selected.map((shot, index) => ({ id: shot.id, index, weight: shot.duration_seconds,
    duration: mode === 'uniform' ? target : target === before ? shot.duration_seconds : 1, remainder: 0 }));
  if (mode === 'total' && target !== before) {
    let remaining = target - selected.length, pending = [...assigned];
    // Redistribute saturated shares; every feasible target remains representable.
    while (pending.length && remaining > 0) {
      const weight = pending.reduce((sum, row) => sum + row.weight, 0);
      const saturated = pending.filter(row => remaining * row.weight >= 599 * weight);
      if (saturated.length) {
        for (const row of saturated) { row.duration = 600; remaining -= 599; }
        const fixed = new Set(saturated); pending = pending.filter(row => !fixed.has(row)); continue;
      }
      for (const row of pending) { row.duration += Math.floor(remaining * row.weight / weight); row.remainder = remaining * row.weight % weight; }
      let extra = target - assigned.reduce((sum, row) => sum + row.duration, 0);
      for (const row of [...pending].sort((a, b) => b.remainder - a.remainder || a.index - b.index)) { if (extra-- <= 0) break; row.duration++; }
      break;
    }
  }
  const durations = new Map(assigned.map(row => [row.id, row.duration]));
  const changes = selected.map(shot => ({ id: shot.id, number: shot.number, before: shot.duration_seconds, after: durations.get(shot.id)! }));
  return { before, after: assigned.reduce((sum, row) => sum + row.duration, 0), changes,
    draft: draft.mode === 'DIRECTOR' ? { ...draft, director_notes: draft.director_notes.map(note => durations.has(note.id) ? { ...note, duration_seconds: durations.get(note.id)! } : note) } : { ...draft, shots: draft.shots.map(shot => durations.has(shot.id) ? { ...shot, duration_seconds: durations.get(shot.id)! } : shot) } };
}
