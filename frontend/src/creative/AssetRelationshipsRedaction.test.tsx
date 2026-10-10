// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import type { StudioAsset, StudioReference, StudioReferences } from './studioClient';

afterEach(cleanup);
it('clears details of a target omitted by a fresh authorized index while preserving authored reason', async () => {
  const asset: StudioAsset = { id: 'source', novel_id: 'project', filename: 'source.png', kind: 'image', media_type: 'image/png', size: 3, sha256: 'a'.repeat(64), version: 2, created_at: '', updated_at: '', relationships: [] };
  const target: StudioReference = { kind: 'ASSET', id: 'private-target', label: '曾可访问的私人标题', version: 4, digest: 'b'.repeat(64), deleted: false };
  const references = vi.fn<() => Promise<StudioReferences>>().mockResolvedValueOnce({ items: [target], read_only: true, content_copied: false }).mockResolvedValueOnce({ items: [], read_only: true, content_copied: false });
  const addRelationship = vi.fn(async () => asset);
  render(<AssetRelationshipsPanel asset={asset} client={{ references, relationships: vi.fn(), addRelationship, removeRelationship: vi.fn() }} canMutate canReview={false} blocked={false} busy={false} isCurrent={() => true} read={operation => operation()} mutate={operation => operation()} onDirtyChange={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
  const option = await screen.findByRole('option', { name: '曾可访问的私人标题 · v4' }) as HTMLOptionElement;
  fireEvent.change(screen.getByLabelText('关联目标'), { target: { value: option.value } }); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '我编写的说明' } });
  expect(document.body.textContent).toContain(target.digest);
  fireEvent.click(screen.getByRole('button', { name: '重新读取引用目录' }));
  await screen.findByText('所选目标已不可用或无权访问，引用详情已清除。关联理由仍保留，请选择其他目标。');
  expect(document.body.textContent).not.toContain(target.label); expect(document.body.textContent).not.toContain(target.digest); expect(document.body.textContent).not.toContain(target.id);
  expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('我编写的说明'); expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(true); expect(addRelationship).not.toHaveBeenCalled();
});
