import { expect, it } from 'vitest';
import { brokerReason, brokerVerification } from './modelBrokerPresentation';
it('explains the missing original vision execution admission without suggesting more quota or credentials', () => {
  const text=brokerReason('VISION_MODEL_ADMISSION_NOT_CONFIGURED');
  expect(text).toContain('真实任务执行链尚未接通');
  expect(text).toContain('模型声明不代表可运行');
  expect(text).toContain('VISION_MODEL_ADMISSION_NOT_CONFIGURED');
  expect(text).not.toContain('购买'); expect(text).not.toContain('密钥');
  expect(brokerVerification('ADAPTER_CONTRACT_ONLY')).toContain('不代表实时可达或生成质量');
});
