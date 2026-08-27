// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,it,vi,expect} from 'vitest';
import {AgentActivityCenter} from './AgentActivityCenter';
import {api} from '../api';
afterEach(cleanup);
it('shows real job activity',async()=>{
  vi.spyOn(api,'agentJobs').mockResolvedValue({items:[{id:'j1',agent_name:'策划 Agent',status:'FAILED',instruction:'规划第二幕',novel_id:'n1',chapter:2,error_code:'TIMEOUT'}],total:1,has_more:false} as any);
  render(<QueryClientProvider client={new QueryClient()}><AgentActivityCenter novelId="n1"/></QueryClientProvider>);
  expect(await screen.findByText('策划 Agent')).toBeTruthy();
  expect(screen.getByText('错误代码：TIMEOUT')).toBeTruthy();
});
it('lists VALIDATED as a terminal contract-check, not a completed creation',async()=>{
  vi.spyOn(api,'agentJobs').mockResolvedValue({items:[{id:'j2',agent_name:'连贯性 Agent',status:'VALIDATED',instruction:'检查冲突',execution_label:'契约校验，未调用模型',novel_id:'n1',chapter:1}],total:1,has_more:false} as any);
  render(<QueryClientProvider client={new QueryClient()}><AgentActivityCenter novelId="n1"/></QueryClientProvider>);
  expect(await screen.findByText('连贯性 Agent')).toBeTruthy();
  expect(screen.getByRole('option',{name:'VALIDATED'})).toBeTruthy();
  expect(screen.getAllByText('VALIDATED').length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText('契约校验，未调用模型')).toBeTruthy();
});
