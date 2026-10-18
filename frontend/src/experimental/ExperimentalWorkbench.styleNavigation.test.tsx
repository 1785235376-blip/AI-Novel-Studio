// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
const flags = { experimental: true, default_enabled: false as const, features: { 'experimental.style_dna_v2': true, 'experimental.visual_embeddings': true } };
const props = { novelId: 'n', context: { sessionToken: '' }, flags, requestedTab: 'style_dna_v2' };
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
beforeEach(() => vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/style-analysis/catalog') ? { styles: [], chapters: [], characters: [], operations: [] } : url.endsWith('/status') ? { status: 'NOT_CONFIGURED' } : { items: [] }), { status: 200 }))));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function edit() { await screen.findByLabelText('Style DNA 标题'); fireEvent.change(screen.getByLabelText('Style DNA 标题'), { target: { value: 'PRIVATE_LOCAL' } }); }
it('tab switching asks, cancellation preserves fields, filtering never asks', async () => {
  render(<ExperimentalWorkbench {...props} />); await edit();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Embedding' } });
  expect(screen.getByDisplayValue('PRIVATE_LOCAL')).toBeTruthy(); expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
  click('视觉 Embedding'); click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('PRIVATE_LOCAL')).toBeTruthy();
  click('视觉 Embedding'); click('放弃 Style DNA 修改并离开'); await screen.findByText('NOT_CONFIGURED');
  expect(screen.queryByDisplayValue('PRIVATE_LOCAL')).toBeNull();
});
it('requestedTab uses the same gate and repeated cancel does not replay a stale request', async () => {
  const view = render(<ExperimentalWorkbench {...props} />); await edit();
  view.rerender(<ExperimentalWorkbench {...props} requestedTab="visual_embeddings" />);
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('PRIVATE_LOCAL')).toBeTruthy();
  view.rerender(<ExperimentalWorkbench {...props} requestedTab="style_dna_v2" />);
  view.rerender(<ExperimentalWorkbench {...props} requestedTab="visual_embeddings" />);
  click('继续编辑 Style DNA'); expect(screen.getByDisplayValue('PRIVATE_LOCAL')).toBeTruthy();
});
it('flag retirement removes private fields and pending intent without asking permission', async () => {
  const view = render(<ExperimentalWorkbench {...props} />); await edit(); click('视觉 Embedding');
  view.rerender(<ExperimentalWorkbench {...props} flags={{ ...flags, features: { ...flags.features, 'experimental.style_dna_v2': false } }} />);
  await waitFor(() => expect(screen.queryByDisplayValue('PRIVATE_LOCAL')).toBeNull());
  expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
  view.rerender(<ExperimentalWorkbench {...props} />); click('风格档案'); await screen.findByLabelText('Style DNA 标题');
  expect(screen.queryByDisplayValue('PRIVATE_LOCAL')).toBeNull();
});

it('selecting the actual active fallback and enabling another tool never drops dirty input', async () => {
  const view = render(<ExperimentalWorkbench {...props} requestedTab={undefined} />); await edit(); click('风格档案');
  expect(screen.queryByRole('region', { name: 'Style DNA 未保存修改' })).toBeNull();
  view.rerender(<ExperimentalWorkbench {...props} requestedTab={undefined} flags={{ ...flags, features: { ...flags.features, 'experimental.advanced_planning_v2': true } }} />);
  expect(screen.getByDisplayValue('PRIVATE_LOCAL')).toBeTruthy();
});
