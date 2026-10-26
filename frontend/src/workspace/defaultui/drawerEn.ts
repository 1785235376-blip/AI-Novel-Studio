// [HERMIA-FE-20261025 UWPORT-P2] Rough English for the task/result/history panels reused in the default-UI drawer.
// Display-only: zh stays byte-identical; unknown strings pass through unchanged (never a raw key).
import {useCallback} from 'react';
import {useLocale} from '../../i18n';

const EXACT: Record<string, string> = {
  '正在读取任务…': 'Loading tasks…', '这个项目还没有任务。': 'No tasks in this project yet.', '任务列表': 'Task list',
  ' · 需核对': ' · needs check', ' 服务端已截断，部分任务未显示。': ' Server truncated the list; some tasks are hidden.',
  '任务分页': 'Task pages', '上一页': 'Prev', '下一页': 'Next', '刷新': 'Refresh', '按媒介筛选': 'Filter by media',
  '任务详情': 'Task details', '状态：': 'Status: ', '（状态需核对：请到原任务界面确认，不会自动重试）': ' (status needs checking in the original task view; no auto retry)',
  '重新读取这个任务失败：它可能已被删除或失效。列表里的信息可能已过时。': 'Re-reading this task failed: it may be deleted or invalid. List info may be outdated.',
  '来源：': 'Source: ', '：': ': ', '生产任务': 'production job', '任务中心': 'task center', '，记录了来源作品节点': ', source node recorded', '，没有记录来源作品节点': ', no source node recorded',
  '成本：未知（服务端没有提供估算）': 'Cost: unknown (no server estimate)', '定位来源节点': 'Locate source node', '查看执行画布': 'Open execution canvas', '返回原位置': 'Back',
  '服务端任务列表不分页：这里是对已读取的有限列表在本机分页显示。': 'Server task list is not paged: this pages the loaded (limited) list locally.',
  '全部': 'All', '图片': 'Image', '音频': 'Audio',
  '排队中': 'Queued', '运行中': 'Running', '准备发送': 'Preparing to send', '远端运行中': 'Running remotely', '结果已返回': 'Result returned',
  '等待审核': 'Awaiting review', '已完成': 'Done', '审核中': 'Reviewing', '已通过': 'Approved', '结果未知': 'Result unknown', '失败': 'Failed', '已取消': 'Cancelled',
  '图像任务': 'Image task', '音频任务': 'Audio task', '视频任务': 'Video task', '时间线任务': 'Timeline task', '未命名任务': 'Untitled task',
  '已采用到作品原位置。旧版本仍保留在作品历史里。': 'Adopted into the work. Old version kept in history.',
  '已审核为正式素材。它还没有被采用到作品，需要你另行确认。': 'Approved as an asset. Not adopted into the work yet; confirm separately.',
  '生成结果': 'Results', '还没有读取结果。读取不会触发生成。': 'No result read yet. Reading never triggers generation.',
  '结果操作': 'Result actions', '重新读取原任务': 'Re-read task', '读取结果': 'Read result',
  '审核为正式素材…': 'Approve as asset…', '采用到作品…': 'Adopt into work…', '对照': 'Compare', '写入设定': 'Write to Canon',
  '确认审核': 'Confirm review', '确认把这份候选审核为正式素材？审核不会把它放进作品，也不会写入设定。': 'Approve this candidate as an asset? It will not be put into the work or Canon.',
  '取消': 'Cancel', '确认采用': 'Confirm adopt', '确认恢复': 'Confirm restore',
  '读取历史失败。请检查网络后再点「读取历史」。': 'Failed to read history. Check network and click "Read history" again.',
  '作品历史': 'Work history', '这些记录有什么区别？': 'What do these records mean?', '重新读取历史': 'Re-read history', '读取历史': 'Read history',
  '（当前）': ' (current)', '与当前对比': 'Compare with current', '恢复这个版本…': 'Restore this version…',
  '你当前没有修改这个项目的权限，不能恢复。': 'You lack permission to modify this project; cannot restore.',
  '确认恢复？这会新增一个版本，不会删除任何记录，也不会重新生成。': 'Restore? This adds a new version, deletes nothing and regenerates nothing.',
  '浏览器本地草稿': 'Local browser draft', '只存在这台设备的浏览器里，还没保存到项目。': 'Only in this browser; not saved to the project.',
  '已保存作品': 'Saved work', '已保存到项目的作品版本。': 'A work version saved to the project.',
  '正式素材版本': 'Asset version', '已审核入库的素材版本，内容不可改写。': 'An approved asset version; content is immutable.',
  '任务执行记录': 'Execution record', '一次生成任务的记录；查看它不会重新执行。': 'Record of one generation task; viewing never re-runs it.',
  '找不到这个历史版本，请重新读取历史。': 'Version not found; re-read history.', '这已经是当前版本。': 'This is already the current version.',
  '这个历史版本引用的素材已不可用，服务端不允许恢复。': 'Assets referenced by this version are unavailable; server refuses restore.',
  '这台设备上还有未保存的浏览器本地草稿，它不在下面的历史里。': 'This device has an unsaved local browser draft; it is not in the history below.',
  '作品原位置正在使用这份已审核素材。': 'The work slot currently uses this approved asset.',
  '已通过审核，但作品原位置还没有换成它。采用需要你确认。': 'Approved, but the work slot does not use it yet. Adopting needs your confirmation.',
  '没有可用结果。需要的话请回到原生产入口重新发起。': 'No usable result. Start again from the original production entry if needed.',
  '没能确认这次执行的结果。请先「重新读取原任务」，系统不会自动重跑。': 'Could not confirm this run\'s result. "Re-read task" first; nothing re-runs automatically.',
  '生成成功不等于审核通过；它不会自动进入作品或设定。': 'Generated is not approved; it never enters the work or Canon automatically.',
  '还没有返回候选。可以稍后手动刷新。': 'No candidate yet. Refresh manually later.',
  '仍在处理': 'Still processing', '候选结果（未审核）': 'Candidate (not reviewed)', '已审核素材（未采用）': 'Approved asset (not adopted)', '当前采用': 'Currently adopted',
  '你当前没有修改这个项目的权限。': 'You lack permission to modify this project.',
  '只有未审核的候选才能审核。': 'Only unreviewed candidates can be reviewed.',
  '对照只支持两份正式素材；候选需先审核。': 'Compare needs two approved assets; review candidates first.',
  '结果不会写入设定（Canon）。设定修改请在小说设定里手动进行。': 'Results never write to Canon. Edit Canon manually in novel settings.',
  '（': ' (', '）': ')',
  '标题会改回历史版本': 'Title reverts to that version', '内容与当前版本相同，只会多一条新的版本记录': 'Same as current; only adds a new version record',
  '不会重跑模型、不会重新入队，也不会自动重新采用旧结果': 'No model rerun, no re-queue, no auto re-adopt of old results',
};
const PATTERNS: Array<[RegExp, (...m: string[]) => string]> = [
  [/^已恢复为新的第 (\d+) 版，旧版本都还在。没有重跑任何生成。$/, v => `Restored as new version ${v}; old versions kept. Nothing regenerated.`],
  [/^恢复到第 (\d+) 版会：$/, v => `Restoring to version ${v} will:`],
  [/^将作品原位置换成已审核素材第 (\d+) 版。作品会生成新版本，旧版本保留可恢复。不会重新生成。$/, v => `Replace the work slot with approved asset v${v}. A new work version is created; old ones stay restorable. No regeneration.`],
  [/^会恢复 (\d+) 张已删除的卡片$/, n => `Restores ${n} deleted card(s)`],
  [/^会移除 (\d+) 张之后新增的卡片$/, n => `Removes ${n} card(s) added later`],
  [/^(\d+) 张卡片位置会改回$/, n => `${n} card position(s) revert`],
  [/^(\d+) 张卡片引用的素材会改回历史版本（不会重新生成，也不会改动素材本身）$/, n => `${n} card asset reference(s) revert (no regeneration, assets untouched)`],
  [/^恢复后生成新的第 (\d+) 版；当前第 (\d+) 版和所有旧版本都保留$/, (a, b) => `Creates new version ${a}; current v${b} and all old versions are kept`],
  [/^第 (\d+) 版 · 保存于 (.+?) · 引用 (\d+) 份素材(?:（(\d+) 份已过期或不可用）)?$/, (v, at, r, s) => `v${v} · saved ${at} · ${r} asset ref(s)${s ? ` (${s} stale/unavailable)` : ''}`],
  [/^(图像生成|视频生成|音频生成|时间线导出|生产任务) · 第 (\d+) 版任务记录$/, (o, v) => `${({图像生成: 'Image', 视频生成: 'Video', 音频生成: 'Audio', 时间线导出: 'Timeline export', 生产任务: 'Production'} as Record<string, string>)[o]} · job record v${v}`],
  [/^来源：(.+)$/, s => `Source: ${dz('en', s)}`],
  [/^ · 正式素材第 (\d+) 版$/, v => ` · asset v${v}`],
];
export function dz(locale: string, s: string): string {
  if (locale !== 'en' || !s) return s;
  if (s in EXACT) return EXACT[s];
  for (const [re, f] of PATTERNS) { const m = re.exec(s); if (m) return f(...m.slice(1)); }
  return s;
}
export function useDz(): (s: string) => string { const l = useLocale(); return useCallback((s: string) => dz(l, s), [l]); }
