import { describe, expect, it } from 'vitest';
import { checkedStoryboardReceipt, type StoryboardReceipt, type StoryboardShot } from '../creative/studioStoryboardContract';
import type { DirectorNote } from '../creative/types';
import fixture from '../creative/fixtures/phase4.file-api-storyboard.json';
import {
  bindDraftToReceipt, continuityOf, directorVsShotOverride, DIRECTOR_FIELD_TABLE, imageBindingRef,
  movesToOrder, neighbourOf, orderDraft, orderShots, renumberShots, sendToDraft, shotSummary,
  sourceStaleness, videoBindingRef, visibleOrderShots,
} from './storyboardOps';
import type { DirectorGoal } from './storyboardWorkspaceTypes';

const copy = <T,>(value: T): T => structuredClone(value);
const receipt = (): StoryboardReceipt => checkedStoryboardReceipt(copy(fixture));
const shots = (): StoryboardShot[] => receipt().shots;

/** 一份带正式视频绑定的合成回执：版本针全部由 fixture 自己的文档快照派生。 */
function withVideo(): StoryboardReceipt {
  const base = copy(fixture) as Record<string, unknown>;
  const rows = base.shots as Record<string, unknown>[];
  const target = rows[1];
  target.video_result = {
    asset: { asset_id: 'video-asset', version: 1, digest: 'd'.repeat(64), kind: 'video' },
    source_shot: {
      document_snapshot: { ...(base.document_snapshot as Record<string, unknown>) },
      shot_id: target.shot_id, shot_version: target.shot_version, shot_digest: target.shot_digest,
    },
    job: { id: 'video-job', version: 3, request_digest: 'e'.repeat(64), receipt_digest: 'f'.repeat(64) },
  };
  return checkedStoryboardReceipt(base);
}

function goal(overrides: Partial<DirectorGoal['adopted']> = {}, noteId = 'note-1'): DirectorGoal {
  return {
    kind: 'SCENE', scene_id: 'scene-1', note_id: noteId, number: 1, source_document: null,
    adopted: {
      note: '待审建议', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC',
      duration_seconds: 5, emotion: '', pacing: '', performance: '', blocking: '',
      ...overrides,
    },
    suggestion: null,
  };
}

const withNotes = (noteIds: string[]): StoryboardShot[] => {
  const list = shots();
  list[0] = { ...list[0], shot: { ...list[0].shot, director_note_ids: noteIds } };
  return list;
};

describe('orderShots 保留稳定 Shot ID，只改显示序号', () => {
  it('把镜头移到最前，身份不变、序号前进、其余字段逐字节不变', () => {
    const before = shots();
    const state = orderShots(before, [{ shot_id: 'shot-2', before_shot_id: 'shot-1' }]);
    expect(state.order).toEqual(['shot-2', 'shot-1']);
    expect(state.saved).toBe(false);
    expect(state.renumbered).toEqual(['shot-2', 'shot-1']);
    const after = renumberShots(before, state);
    expect(after.map(shot => shot.shot_id)).toEqual(['shot-2', 'shot-1']);
    expect(after.map(shot => shot.shot.number)).toEqual([1, 2]);
    // 身份与版本针不因为拖动而改变。
    expect(after.map(shot => shot.shot_version)).toEqual([1, 1]);
    expect(after.map(shot => shot.shot_digest))
      .toEqual([before[1].shot_digest, before[0].shot_digest]);
    expect([...after.map(shot => shot.shot_digest)].sort())
      .toEqual([...before.map(shot => shot.shot_digest)].sort());
    expect(after.map(shot => shot.image_asset?.asset_id)).toEqual([before[1].image_asset?.asset_id, before[0].image_asset?.asset_id]);
    expect(after[0].shot.duration_seconds).toBe(before[1].shot.duration_seconds);
    expect(after[1].shot.frame_prompt).toBe(before[0].shot.frame_prompt);
  });

  it('移到末尾与空 move 列表', () => {
    const before = shots();
    expect(orderShots(before, []).saved).toBe(true);
    expect(orderShots(before, []).renumbered).toEqual([]);
    const state = orderShots(before, [{ shot_id: 'shot-1', before_shot_id: null }]);
    expect(state.order).toEqual(['shot-2', 'shot-1']);
    expect(state.saved).toBe(false);
  });

  it('已经在这个位置的 move 是幂等的：saved 维持真、renumbered 为空', () => {
    const state = orderShots(shots(), [{ shot_id: 'shot-1', before_shot_id: 'shot-2' }]);
    expect(state.order).toEqual(['shot-1', 'shot-2']);
    expect(state.saved).toBe(true);
    expect(state.renumbered).toEqual([]);
  });

  it('报告哪些镜头带绑定：原 owner 会丢弃与旧序号不一致的绑定', () => {
    const state = orderShots(shots(), [{ shot_id: 'shot-2', before_shot_id: 'shot-1' }]);
    expect(state.invalidated_bindings.sort()).toEqual(['shot-1', 'shot-2']);
    const video = withVideo();
    const videoState = orderShots(video.shots, [{ shot_id: 'shot-2', before_shot_id: 'shot-1' }]);
    expect(videoState.invalidated_bindings).toContain('shot-2');
  });

  it('未知身份 / 重复身份 / 自指 / 重复目标一律本地拒绝，并有稳定机器码', () => {
    const before = shots();
    const codeOf = (run: () => unknown) => {
      try { run(); return 'NO_THROW'; } catch (reason) { return (reason as { problem?: { code?: string } }).problem?.code; }
    };
    expect(codeOf(() => orderShots(before, [{ shot_id: 'missing', before_shot_id: null }])))
      .toBe('STUDIO_STORYBOARD_ORDER_LOCAL_INVALID');
    expect(codeOf(() => orderShots(before, [{ shot_id: 'shot-1', before_shot_id: 'shot-1' }])))
      .toBe('STUDIO_STORYBOARD_ORDER_LOCAL_INVALID');
    expect(codeOf(() => orderShots(before, [
      { shot_id: 'shot-1', before_shot_id: null }, { shot_id: 'shot-1', before_shot_id: null },
    ]))).toBe('STUDIO_STORYBOARD_ORDER_LOCAL_INVALID');
    expect(codeOf(() => orderShots([before[0], before[0]], [])))
      .toBe('STUDIO_STORYBOARD_ORDER_LOCAL_INVALID');
  });

  it('movesToOrder 能把任意目标顺序折算成 move，并还原同一个顺序', () => {
    const before = shots();
    const moves = movesToOrder(before, ['shot-2', 'shot-1']);
    expect(orderShots(before, moves).order).toEqual(['shot-2', 'shot-1']);
    expect(movesToOrder(before, ['shot-1', 'shot-2'])).toEqual([]);
    expect(() => movesToOrder(before, ['shot-1'])).toThrowError();
  });

  it('orderDraft 与 visibleOrderShots 与 orderShots 一致', () => {
    const before = shots();
    const state = orderShots(before, [{ shot_id: 'shot-2', before_shot_id: 'shot-1' }]);
    const draft = orderDraft(before, state);
    expect(draft).toEqual({
      shot_ids: ['shot-2', 'shot-1'], saved: false, renumbered: ['shot-2', 'shot-1'],
      approval_effect: 'REVOKES_APPROVAL_AND_DROPS_MISMATCHED_BINDINGS',
      invalidated_bindings: ['shot-2', 'shot-1'],
    });
    expect(visibleOrderShots(before, [{ shot_id: 'shot-2', before_shot_id: 'shot-1' }]).map(shot => shot.shot_id))
      .toEqual(['shot-2', 'shot-1']);
  });
});

describe('neighbourOf 在边界处如实返回 null', () => {
  it('第一个镜头没有前一个，最后一个没有后一个，且不回绕', () => {
    const before = shots();
    expect(neighbourOf(before, 'shot-1', 'PREVIOUS')).toBeNull();
    expect(neighbourOf(before, 'shot-1', 'NEXT')?.shot_id).toBe('shot-2');
    expect(neighbourOf(before, 'shot-2', 'NEXT')).toBeNull();
    expect(neighbourOf(before, 'shot-2', 'PREVIOUS')?.shot_id).toBe('shot-1');
  });

  it('未知镜头返回 null，未知方向本地拒绝', () => {
    const before = shots();
    expect(neighbourOf(before, 'missing', 'NEXT')).toBeNull();
    expect(() => neighbourOf(before, 'shot-1', 'SIDEWAYS' as 'NEXT')).toThrowError();
  });

  it('只报告 owner 声明的邻居，不推断', () => {
    const before = shots();
    expect(continuityOf(before[0], 'NEXT')).toBe('shot-2');
    expect(continuityOf(before[0], 'PREVIOUS')).toBeNull();
    expect(continuityOf(before[1], 'PREVIOUS')).toBe('shot-1');
  });
});

describe('shotSummary 只报告 owner 事实，绝不发明值', () => {
  it('读到的事实进入 evidence.fields，缺席的进入 evidence.absent', () => {
    const summary = shotSummary(shots()[0]);
    expect(summary.shot_id).toBe('shot-1');
    expect(summary.number).toBe(1);
    expect(summary.scene_id).toBe('scene-1');
    expect(summary.duration).toEqual({ seconds: 3, source: 'SHOT' });
    expect(summary.framing.shot_size).toBe('MEDIUM');
    expect(summary.framing.lens).toBeNull();
    expect(summary.lighting_color.lighting).toBe('Soft key');
    expect(summary.evidence.fields).toContain('duration_seconds');
    expect(summary.evidence.fields).toContain('image_binding');
    expect(summary.evidence.absent).toContain('audio');
    expect(summary.evidence.absent).toContain('director_note_ids');
    expect(summary.evidence.absent).not.toContain('duration_seconds');
  });

  it('没有对白/音效时 audio 是 null，不补一个空字符串对象', () => {
    expect(shotSummary(shots()[0]).audio).toBeNull();
    const loud = shots();
    loud[0] = { ...loud[0], shot: { ...loud[0].shot, sound_effect: '风声', sound: '' } };
    expect(shotSummary(loud[0]).audio).toEqual({ sound_effect: '风声', sound: null });
  });

  it('continuity 缺失时是 null，不会声称"连续性一致"', () => {
    const list = shots();
    list[1] = { ...list[1], shot: { ...list[1].shot, continuity: null } };
    expect(shotSummary(list[1]).references.continuity).toBeNull();
    expect(shotSummary(shots()[1]).references.continuity?.previous_shot_id).toBe('shot-1');
  });

  it('候选来源优先视频，再图片；两者都缺席就是 null', () => {
    const video = withVideo();
    expect(shotSummary(video.shots[1]).candidate?.kind).toBe('VIDEO');
    expect(shotSummary(video.shots[0]).candidate?.kind).toBe('IMAGE');
    const none = shots().map(shot => ({ ...shot, image_asset: null }));
    expect(shotSummary(none[0]).candidate).toBeNull();
  });

  it('下一步动作由 owner 事实推出：先绑定图片，绑了图片才谈时间线', () => {
    // 这个 fixture 的两个镜头都已经绑定正式图片，所以"预备图片草稿"不出现。
    expect(shotSummary(shots()[0]).next_actions).not.toContain('PREPARE_IMAGE_DRAFT');
    expect(shotSummary(shots()[0]).next_actions).toContain('COMPARE_REFERENCE');
    expect(shotSummary(shots()[0]).next_actions).toContain('PREPARE_TIMELINE_DRAFT');
    const unbound = shots().map(shot => ({ ...shot, image_asset: null }));
    expect(shotSummary(unbound[0]).next_actions).toContain('PREPARE_IMAGE_DRAFT');
    expect(shotSummary(unbound[0]).next_actions).not.toContain('PREPARE_TIMELINE_DRAFT');
    expect(shotSummary(unbound[0]).next_actions).not.toContain('COMPARE_REFERENCE');
  });

  it('越界文本与不完整镜头本地拒绝，不显示半真数据', () => {
    const long = shots();
    long[0] = { ...long[0], shot: { ...long[0].shot, shot_size: 'x'.repeat(81) } };
    expect(() => shotSummary(long[0])).toThrowError();
    expect(() => shotSummary(undefined as unknown as StoryboardShot)).toThrowError();
    expect(() => shotSummary({ shot_id: '' } as unknown as StoryboardShot)).toThrowError();
  });

  it('imageBindingRef / videoBindingRef 只复制 owner 明写的版本', () => {
    expect(imageBindingRef(shots()[0])).toEqual({
      asset_id: '68bc2dce-60c3-4285-b8c4-aea92944588f', version: 2,
      digest: 'e44c53d995048ed9946460ee419333f679240806c26632cf21c517eb934667a4',
    });
    expect(videoBindingRef(shots()[0])).toBeNull();
    const video = withVideo();
    expect(videoBindingRef(video.shots[1])?.job.request_digest).toBe('e'.repeat(64));
    expect(videoBindingRef(video.shots[1])?.source_shot.shot_version).toBe(1);
  });
});

describe('directorVsShotOverride 显示继承与镜头级覆写，且不改动导演文档', () => {
  it('镜头没有关联备注时明说没有继承依据', () => {
    const resolution = directorVsShotOverride(goal(), shots()[0]);
    expect(resolution.inherited_from_note_ids).toEqual([]);
    expect(resolution.fields.find(field => field.field === 'shot_size')?.effective).toBe('SHOT_OVERRIDE');
    expect(resolution.fields.find(field => field.field === 'shot_size')?.inherited_value).toBeNull();
    expect(resolution.downstream).toBe('DIRECTOR_GOAL_EDIT_DOES_NOT_OVERWRITE_APPROVED_RESULTS');
  });

  it('关联备注且值不同时，镜头级覆写生效并标记 overridden', () => {
    const list = withNotes(['note-1']);
    const resolution = directorVsShotOverride(goal({ shot_size: 'WIDE' }), list[0]);
    expect(resolution.inherited_from_note_ids).toEqual(['note-1']);
    const field = resolution.fields.find(item => item.field === 'shot_size');
    expect(field).toMatchObject({ shot_value: 'MEDIUM', inherited_value: 'WIDE', effective: 'SHOT_OVERRIDE', overridden: true });
  });

  it('值相同时报告继承（而不是"覆写"）', () => {
    const list = withNotes(['note-1']);
    const resolution = directorVsShotOverride(goal({ shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL' }), list[0]);
    expect(resolution.fields.find(item => item.field === 'shot_size'))
      .toMatchObject({ effective: 'DIRECTOR_INHERITED', overridden: false });
  });

  it('导演独有的 pacing/performance 永远算继承，不会被说成镜头覆写', () => {
    const list = withNotes(['note-1']);
    const resolution = directorVsShotOverride(goal({ pacing: '慢', performance: '停顿' }), list[0]);
    expect(resolution.fields.find(item => item.field === 'pacing'))
      .toMatchObject({ shot_value: null, inherited_value: '慢', effective: 'DIRECTOR_INHERITED', overridden: false });
    expect(resolution.fields.find(item => item.field === 'performance')?.effective).toBe('DIRECTOR_INHERITED');
  });

  it('对比覆盖整张字段表，且不修改传入的导演目标或镜头', () => {
    const list = withNotes(['note-1']);
    const source = goal({ shot_size: 'WIDE' });
    const snapshot = JSON.stringify({ goal: source, shot: list[0] });
    const resolution = directorVsShotOverride(source, list[0]);
    expect(resolution.fields.map(field => field.field)).toEqual([...DIRECTOR_FIELD_TABLE]);
    expect(JSON.stringify({ goal: source, shot: list[0] })).toBe(snapshot);
  });

  it('导演文档版本针来自原文档，不由这里生成', () => {
    const withSource = { ...goal(), source_document: { id: 'director-doc', version: 7, digest: 'a'.repeat(64) } };
    expect(directorVsShotOverride(withSource, shots()[0]).director_document)
      .toEqual({ id: 'director-doc', version: 7, digest: 'a'.repeat(64) });
  });
});

describe('sendToDraft 只是草稿：精确到原版本，没有执行意图', () => {
  it('返回目标、镜头身份、镜头版本与摘要；文档版本必须由原回执补齐', () => {
    const draft = sendToDraft('IMAGE', shots()[0]);
    expect(draft.target).toBe('IMAGE');
    expect(draft.document_version).toBeNull();
    expect(draft.shot_id).toBe('shot-1');
    expect(draft.shot_version).toBe(1);
    expect(draft.source_digest).toBe(shots()[0].shot_digest);
    expect(Object.keys(draft).sort()).toEqual(['bindings', 'document_version', 'order_shot_ids', 'shot_id', 'shot_version', 'source_digest', 'target']);
    expect(JSON.stringify(draft)).not.toMatch(/request_id|dispatch|queue/i);
  });

  it('绑定只复制原文档里已经存在的版本', () => {
    const video = withVideo();
    expect(sendToDraft('VIDEO', video.shots[1]).bindings.IMAGE)
      .toEqual({ asset_id: '68bc2dce-60c3-4285-b8c4-aea92944588f', version: 2, digest: 'e44c53d995048ed9946460ee419333f679240806c26632cf21c517eb934667a4' });
    expect(sendToDraft('VIDEO', video.shots[1]).bindings.VIDEO?.job.id).toBe('video-job');
    expect(sendToDraft('IMAGE', video.shots[0]).bindings.VIDEO).toBeNull();
  });

  it('没有正式图片时不形成视频/时间线草稿，并给出本地机器码', () => {
    const unbound = shots().map(shot => ({ ...shot, image_asset: null }));
    const codeOf = (run: () => unknown) => {
      try { run(); return 'NO_THROW'; } catch (reason) { return (reason as { problem?: { code?: string } }).problem?.code; }
    };
    expect(codeOf(() => sendToDraft('VIDEO', unbound[0]))).toBe('STUDIO_STORYBOARD_SEND_LOCAL_INVALID');
    expect(codeOf(() => sendToDraft('TIMELINE', unbound[0]))).toBe('STUDIO_STORYBOARD_SEND_LOCAL_INVALID');
    expect(sendToDraft('IMAGE', unbound[0]).bindings.IMAGE).toBeNull();
  });

  it('未声明的目标在本地就被拒绝', () => {
    const codeOf = (run: () => unknown) => {
      try { run(); return 'NO_THROW'; } catch (reason) { return (reason as { problem?: { code?: string } }).problem?.code; }
    };
    expect(codeOf(() => sendToDraft('AUDIO' as 'IMAGE', shots()[0]))).toBe('STUDIO_STORYBOARD_TARGET_NOT_DECLARED');
  });

  it('bindDraftToReceipt 用已核对的原回执补文档版本与时间线顺序', () => {
    const base = receipt();
    const draft = sendToDraft('TIMELINE', base.shots[0]);
    const bound = bindDraftToReceipt(draft, base, ['shot-2', 'shot-1']);
    expect(bound.document_version).toBe(base.document_snapshot.version);
    expect(bound.order_shot_ids).toEqual(['shot-2', 'shot-1']);
  });

  it('镜头版本或顺序对不上时本地拒绝，绝不提交一张可疑草稿', () => {
    const base = receipt();
    const stale = { ...sendToDraft('IMAGE', base.shots[0]), shot_version: 9 };
    expect(() => bindDraftToReceipt(stale, base)).toThrowError();
    expect(() => bindDraftToReceipt(sendToDraft('TIMELINE', base.shots[0]), base, ['shot-1', 'missing'])).toThrowError();
    expect(() => bindDraftToReceipt(sendToDraft('TIMELINE', base.shots[0]), base, ['shot-1', 'shot-1'])).toThrowError();
  });
});

describe('sourceStaleness 只在有证据时报告不一致', () => {
  it('没有任何证据时是空数组（不是"连续性没问题"）', () => {
    expect(sourceStaleness(shots()[0])).toEqual([]);
    expect(sourceStaleness(shots()[1])).toEqual([]);
  });

  it('上游文档读不到 → DIRECTOR_SOURCE_UNAVAILABLE，并带上原版本针', () => {
    const notes = sourceStaleness(shots()[0], { sources: { 'director-doc': { version: 4, digest: 'a'.repeat(64) } } });
    expect(notes).toHaveLength(1);
    expect(notes[0].kind).toBe('DIRECTOR_SOURCE_UNAVAILABLE');
    expect(notes[0].expected).toEqual({ id: 'director-doc', version: 4, digest: 'a'.repeat(64) });
    expect(notes[0].actual).toBeNull();
  });

  it('上游文档版本或摘要变化 → DIRECTOR_SOURCE_CHANGED，两侧都给证据', () => {
    const notes = sourceStaleness(shots()[0], {
      sources: { 'director-doc': { version: 4, digest: 'a'.repeat(64) } },
      knownDocuments: { 'director-doc': { version: 5, digest: 'b'.repeat(64) } },
    });
    expect(notes[0].kind).toBe('DIRECTOR_SOURCE_CHANGED');
    expect(notes[0].actual).toEqual({ id: 'director-doc', version: 5, digest: 'b'.repeat(64) });
  });

  it('上游一致时什么都不报告', () => {
    expect(sourceStaleness(shots()[0], {
      sources: { 'director-doc': { version: 4, digest: 'a'.repeat(64) } },
      knownDocuments: { 'director-doc': { version: 4, digest: 'a'.repeat(64) } },
    })).toEqual([]);
  });

  it('已绑定视频来自快门版本 → CANDIDATE_SOURCE_SHOT_CHANGED', () => {
    const video = withVideo();
    const stale = video.shots.map(shot => shot.shot_id === 'shot-2'
      ? { ...shot, video_result: { ...shot.video_result!, source_shot: { ...shot.video_result!.source_shot, shot_version: 3 } } }
      : shot);
    const notes = sourceStaleness(stale[1]);
    expect(notes.map(note => note.kind)).toEqual(['CANDIDATE_SOURCE_SHOT_CHANGED']);
    expect(notes[0].actual?.version).toBe(3);
  });

  it('没有被记下的上游文档就不会被报告（不猜）', () => {
    expect(sourceStaleness(shots()[0], { knownDocuments: { 'other-doc': { version: 1, digest: 'c'.repeat(64) } } })).toEqual([]);
  });
});

describe('导演备注辅助断言（不参与生产代码，只固定 fixture 事实）', () => {
  it('fixture 的两个镜头都没有关联导演备注，因此继承结论必须显式为"无"', () => {
    const list = shots();
    for (const shot of list) expect(shot.shot.director_note_ids ?? []).toEqual([]);
    const note = { id: 'note-1' } as DirectorNote;
    expect(note.id).toBe('note-1');
  });
});
