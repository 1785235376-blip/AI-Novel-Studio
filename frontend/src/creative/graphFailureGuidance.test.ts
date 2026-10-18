import { expect, it } from 'vitest';
import { graphFailureGuidance } from './graphFailureGuidance';
it('maps original input, dependency, reference and capability codes conservatively', () => {
  expect(graphFailureGuidance('CREATIVE_GRAPH_REQUIRED_INPUT_MISSING')).toContain('必需输入连接');
  expect(graphFailureGuidance('CREATIVE_GRAPH_UPSTREAM_OUTPUT_MISSING')).toContain('上游审核回执');
  expect(graphFailureGuidance('CREATIVE_GRAPH_DISABLED_DEPENDENCY')).toContain('此节点或上游节点');
  expect(graphFailureGuidance('CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED')).toContain('权限、版本和内容');
  expect(graphFailureGuidance('CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED')).toContain('schema');
  expect(graphFailureGuidance('CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE')).toContain('缺少所需原处理能力');
});
it.each([undefined, 'UNKNOWN', 'CREATIVE_GRAPH_NODE_FAILED', 'UNRECOGNIZED'])('does not infer retryability or outcome from %s', code => {
  expect(graphFailureGuidance(code)).toContain('结果未知时保留原请求身份');
  expect(graphFailureGuidance(code)).toContain('此提示不代表可以重试');
});
