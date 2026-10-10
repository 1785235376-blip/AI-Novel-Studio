import { Badge, StatusMessage } from '../ui/primitives';
import type { StudioGraphTextAssetOutput } from './studioGraphTextAssetTypes';
const labels = { PENDING: '等待核对', INCOMPLETE: '存储未完成', NO_ACCEPTED_RESULT: '没有可采用结果', DRAFT: '待审核', APPROVED: '已批准', REJECTED: '已驳回' };
export function GraphTextAssetSummary({ output }: { output: StudioGraphTextAssetOutput }) {
  return <section className="studio-graph-model" aria-label="私有文字资产回执">
    <h4>私有文字资产</h4><Badge tone={output.state === 'INCOMPLETE' ? 'warning' : 'neutral'}>{labels[output.state]}</Badge>
    <p>仅当前创作者可见；未写入正文。质量验收：未运行。不会自动重试模型。</p>
    {output.state === 'PENDING' && <p>结果归档待核对。读取当前运行时会核对存储，不会重试模型。</p>}
    {output.state === 'INCOMPLETE' && <StatusMessage tone="warning">存储步骤未完成，结果暂不可审核。请重新读取当前运行以核对归档；模型不会重新调用。{output.reason}</StatusMessage>}
    {output.state === 'NO_ACCEPTED_RESULT' && <p>本次运行没有可采用的文字资产。</p>}
    {output.asset_id !== null && <>
      <p>资产：{output.asset_id} · v{output.version} · {output.size} 字节 · text/plain</p>
      <p>模型：{output.provider_id} / {output.model_id}{output.parameters.synthetic ? ' · 测试适配器' : ''} · 最多 {output.parameters.max_output_tokens} 输出 token · 温度 {output.parameters.temperature}</p>
      <details><summary>核对文字资产来源</summary>
        <p>图：{output.source.graph_id} · v{output.source.graph_version} · 运行：{output.source.run_id} · 来源 v{output.source.source_run_version}</p>
        <p>模型节点：{output.source.model_node_id} · 原任务：{output.source.job_id}</p>
        <p>图摘要：{output.source.graph_digest}</p><p>输入摘要：{output.source.input_digest}</p><p>预览摘要：{output.source.preview_digest}</p><p>文字 SHA-256：{output.sha256}</p>
        <p>生成：{output.source.produced_at} · 建立：{output.created_at} · 更新：{output.updated_at}</p>
      </details>
    </>}
  </section>;
}
