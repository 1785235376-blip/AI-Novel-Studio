import { expect, it } from 'vitest';
import { brokerCost, brokerReason, brokerVerification } from './modelBrokerPresentation';
it('keeps USD units, synthetic zero and unknown distinct without rounding micro amounts away', () => {
  expect(brokerCost(1)).toBe('0.000001 USD（1 µUSD）');
  expect(brokerCost(0)).toBe('0 USD（0 µUSD）');
  expect(brokerCost(null)).toBe('未知（不能当作免费）');
  expect(brokerCost(Number.NaN)).toBe('未知（不能当作免费）');
});
it('does not infer connectivity or hardware failure from declarations or unknown evidence', () => {
  expect(brokerVerification('ADAPTER_CONTRACT_ONLY')).toContain('连接未验证');
  expect(brokerVerification('FUTURE_CODE')).toContain('连接未验证');
  expect(brokerVerification('SYNTHETIC_PROTOCOL_ONLY')).toContain('仅合成协议测试');
  expect(brokerReason('HOST_CAPACITY_UNKNOWN_OR_INSUFFICIENT')).toContain('不能据此断言机器无法运行模型');
  expect(brokerReason('FUTURE_CODE')).toBe('FUTURE_CODE');
});
