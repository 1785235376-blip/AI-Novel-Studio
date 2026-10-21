import type { CanvasAudioTemplateParameters } from './canvasAudioWorkflowTemplate';

const fields = [
  ['in_ms', '来源起点', 'ms'], ['out_ms', '来源终点', 'ms'], ['gain_db', '增益', 'dB'],
  ['fade_in_ms', '淡入', 'ms'], ['fade_out_ms', '淡出', 'ms'],
] as const;
const shown = (value: unknown, unit: string) => typeof value === 'number' && Number.isFinite(value) ? `${value} ${unit}` : '尚未核对';

/** Readonly parameter comparison; copying and execution remain owned by the original task. */
export function CanvasAudioTemplateParameterComparison({ source, current }: { source: CanvasAudioTemplateParameters; current?: CanvasAudioTemplateParameters }) {
  return <table aria-label="模板参数与本次任务对照">
    <thead><tr><th scope="col">参数</th><th scope="col">模板值</th><th scope="col">本次任务当前值</th><th scope="col">复制后</th></tr></thead>
    <tbody>{fields.map(([key, label, unit]) => {
      const provided = Object.hasOwn(source, key);
      return <tr key={key}><th scope="row">{label}</th>
        <td>{provided ? shown(source[key], unit) : '未提供'}</td>
        <td>{current && Object.hasOwn(current, key) ? shown(current[key], unit) : '未提供当前值'}</td>
        <td>{provided ? `${shown(source[key], unit)}（本次覆盖）` : '保留本次设置'}</td>
      </tr>;
    })}</tbody>
  </table>;
}

/** Applied template provenance: compare the pinned source with actual task overrides. */
export function AudioTemplateParametersComparison({ templateParameters, currentParameters }: {
  templateParameters: CanvasAudioTemplateParameters;
  currentParameters?: CanvasAudioTemplateParameters;
}) {
  return <table aria-label="已应用模板与本次任务参数对照">
    <thead><tr><th scope="col">参数</th><th scope="col">源模板版本值</th><th scope="col">本次任务当前值</th><th scope="col">本次覆盖状态</th></tr></thead>
    <tbody>{fields.map(([key, label, unit]) => {
      const supplied = Object.hasOwn(templateParameters, key);
      const present = !!currentParameters && Object.hasOwn(currentParameters, key);
      const value = currentParameters?.[key];
      const valid = typeof value === 'number' && Number.isFinite(value);
      const status = !present || !valid ? '尚未核对当前值'
        : !supplied ? '模板未提供 · 保留本次值'
        : value === templateParameters[key] ? '与源模板一致' : '仅本次任务覆盖';
      return <tr key={key}><th scope="row">{label}</th>
        <td>{supplied ? shown(templateParameters[key], unit) : '未提供'}</td>
        <td>{present ? shown(value, unit) : '未提供当前值'}</td>
        <td>{status}</td>
      </tr>;
    })}</tbody>
  </table>;
}
