// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { ScreenplayExportPanel } from './ScreenplayExportPanel';
import { newDocument, newScene, type CreativeDocument } from './types';
import type { CreativeClient } from './client';

afterEach(cleanup);

it.each(['SCREENPLAY', 'SCRIPT'] as const)('gives %s export selection an exact name independent of option text', mode => {
  const document = { ...newDocument(mode), id: 'saved-document', version: 1, scenes: mode === 'SCREENPLAY' ? [newScene(1)] : [] } as CreativeDocument;
  render(<ScreenplayExportPanel client={{} as CreativeClient} document={document} available={true} onDenied={vi.fn()} />);
  expect(screen.getByRole('combobox').getAttribute('aria-label')).toBe(mode === 'SCRIPT' ? '脚本导出格式' : '剧本导出格式');
});

it('gives Script purpose an exact name independent of translated option labels', () => {
  render(<CreativeCanvas draft={newDocument('SCRIPT')} dirty={false} canEdit={true} busy={false}
    onScene={vi.fn()} onShot={vi.fn()} onChange={vi.fn()} onSave={vi.fn()} onNew={vi.fn()} />);
  expect(screen.getByRole('combobox').getAttribute('aria-label')).toBe('脚本用途');
});
