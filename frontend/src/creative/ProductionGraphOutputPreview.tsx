import type { StudioGraphOutput } from './studioGraphTypes';

/** Typed read-only preview over the original workflow output and original document owner. */
export function ProductionGraphOutputPreview({ output }: { output: StudioGraphOutput | null }) {
  const director = output?.direction && 'content' in output.direction ? output.direction : undefined;
  const projection = director || output?.storyboard;
  return <>{projection && <details><summary>{director ? '查看导演节点输出' : '查看分镜节点输出'}</summary>
    <p>{projection.content.title} · 原文档 v{projection.document_snapshot.version}</p><code>{projection.document_snapshot.digest}</code>
    {projection.content.visual_target && <p>视觉目标：{[projection.content.visual_target.style, projection.content.visual_target.atmosphere, projection.content.visual_target.color, projection.content.visual_target.rhythm].filter(Boolean).join(' · ')}</p>}
    {director ? <ol>{projection.content.director_notes.map(note => <li key={note.id}><strong>调度 {note.number} · {note.scene_id}</strong><p>{note.note}</p><p>{note.shot_suggestion || note.shot_size} · {note.camera_angle} · {note.camera_motion} · {note.duration_seconds} 秒</p><p>{note.emotion} · {note.pacing} · {note.character_state}</p>{note.performances?.map(performance => <p key={performance.character}>{performance.character}：{[performance.action, performance.expression, performance.state].filter(Boolean).join(' · ')}</p>)}</li>)}</ol>
      : <ol>{projection.content.shots.map(shot => <li key={shot.id}><strong>SHOT {shot.number} · {shot.id}</strong><p>{shot.frame_prompt || shot.action}</p><p>{shot.shot_size} · {shot.camera_angle} · {shot.camera_motion} · {shot.lens} · {shot.duration_seconds} 秒</p><p>{shot.composition} · {shot.emotion} · {shot.sound || shot.sound_effect}</p></li>)}</ol>}
    <p>原文档版本的只读输出。连接不会覆盖作者内容或自动执行图片、视频。</p>
  </details>}{output?.prompt && <details><summary>查看图片提示词与来源</summary><pre>{output.prompt.prompt}</pre><p>{output.prompt.references.length} 张版本绑定参考图</p>{output.prompt.document_sources?.map(source => <p key={source.id}>原文档 {source.id} · v{source.version} · <code>{source.digest}</code></p>)}</details>}</>;
}
