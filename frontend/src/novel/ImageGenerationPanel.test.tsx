// @vitest-environment jsdom
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {ImageGenerationPanel} from './ImageGenerationPanel';
import {api} from '../api';
import {vi,it,expect,afterEach} from 'vitest';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

it('exposes real task lifecycle and only renders URI after generation resolves', async()=>{
  vi.spyOn(api,'imageGenerations').mockResolvedValue({items:[]});
  vi.spyOn(api,'assetProviders').mockResolvedValue({items:[{provider_id:'ddshub',default_model:'gpt-image-2',configured:true,registered:true}]});
  let resolve!: (value:any)=>void;
  vi.spyOn(api,'imageGenerate').mockImplementation(()=>new Promise(r=>{resolve=r}));
  const inspect=vi.fn();
  render(<ImageGenerationPanel novelId="n1" onInspect={inspect}/>);
  await waitFor(()=>expect((screen.getByRole('button',{name:'生成图片'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'生成图片'}));
  expect(screen.getByText('任务状态：执行中')).toBeTruthy();
  expect(screen.queryByAltText('生成结果')).toBeNull();
  resolve({asset_uri:'https://example.test/image.png'});
  await waitFor(()=>expect(screen.getByAltText('生成结果')).toBeTruthy());
  expect(screen.getByText('任务状态：已完成')).toBeTruthy();
  expect(inspect).toHaveBeenLastCalledWith(expect.objectContaining({id:'image-task',status:'SUCCEEDED',providerId:'ddshub',modelId:'gpt-image-2',assetUri:'https://example.test/image.png'}));
  expect(inspect.mock.calls.at(-1)?.[0]).not.toHaveProperty('prompt');
});

it('marks failed requests without fabricating an image URI', async()=>{
  vi.spyOn(api,'imageGenerations').mockResolvedValue({items:[]});
  vi.spyOn(api,'assetProviders').mockResolvedValue({items:[{provider_id:'ddshub',default_model:'gpt-image-2',configured:true,registered:true}]});
  vi.spyOn(api,'imageGenerate').mockRejectedValue(new Error('offline'));
  render(<ImageGenerationPanel novelId="n1"/>);
  await waitFor(()=>expect((screen.getByRole('button',{name:'生成图片'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'生成图片'}));
  await waitFor(()=>expect(screen.getByText('任务状态：失败 · 图片生成失败，请检查 Provider 配置。')).toBeTruthy());
  expect(screen.queryByAltText('生成结果')).toBeNull();
});
