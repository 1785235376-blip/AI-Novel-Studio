// @vitest-environment jsdom
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import receipt from '../../../tests/fixtures/studio_cfg_receipt.json';
import { studioProductionClient } from './studioProductionClient';
import { StudioExecutionRecipePanel } from './StudioExecutionRecipePanel';
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('reads actual File-produced cfg provider, preview and Job receipts and explains the recorded KSampler zero', async () => {
  const fetcher = vi.fn(async (url: string) => response(url.endsWith('/providers') ? receipt.providers : url.endsWith('/preview') ? receipt.preview : receipt.job));
  vi.stubGlobal('fetch', fetcher); const client = studioProductionClient(receipt.project, { sessionToken: '' });
  const providers = await client.providers(), provider = providers.find(p=>p.operation_id==='m5.image.t2i'&&p.provider_id===receipt.preview.command.provider_id)!;
  expect(provider.supported_parameters).toContain('cfg'); expect(provider.image_capabilities?.cfg).toEqual({ min: 0, max: 100, default: 7 });
  const preview = await client.preview(receipt.preview.command as never), job = await client.get('image', receipt.job.id);
  expect(preview.command.parameters.cfg).toBe(0); expect(job.command!.parameters.cfg).toBe(0);
  render(<StudioExecutionRecipePanel recipe={job.execution_recipe} operationId="m5.image.t2i" current />);
  expect(screen.getByText((_,element)=>element?.tagName==='LI'&&element.textContent==='cfg：FLOAT · 配方记录值 0')).toBeTruthy(); expect(fetcher).toHaveBeenCalledTimes(3);
});
it.each(['cloud capability','bad bounds','mismatched recipe cfg'] as const)('rejects cfg receipt contract corruption: %s', kind => {
  const value = structuredClone(kind==='mismatched recipe cfg' ? receipt.preview : receipt.providers) as any;
  if(kind==='mismatched recipe cfg') value.execution_recipe.workflow['3'].inputs.cfg=7;
  else {const item=value.items.find((p:any)=>p.operation_id==='m5.image.t2i'&&p.image_capabilities?.cfg); if(kind==='cloud capability')item.local=false;else item.image_capabilities.cfg.max=6;}
  vi.stubGlobal('fetch',vi.fn(async()=>response(value))); const client=studioProductionClient(receipt.project,{sessionToken:''});
  return expect(kind==='mismatched recipe cfg'?client.preview(receipt.preview.command as never):client.providers()).rejects.toThrow();
});
