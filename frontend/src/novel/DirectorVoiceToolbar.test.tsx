// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DirectorVoiceToolbar } from './DirectorVoiceToolbar';
vi.mock('../api', () => ({ api: { synthesizeDirectorShots: vi.fn().mockResolvedValue([]) } }));
describe('DirectorVoiceToolbar', () => { it('exposes explicit generation and export actions', () => { render(<DirectorVoiceToolbar shots={[{ shot_id:'a', name:'一', duration:'2s', camera:'', action:'', dialogue:'开始', voice:'hero' }]} batch={[]} onBatch={vi.fn()} />); expect(screen.getByText('生成全部可用配音')).toBeTruthy(); expect(screen.getByText('导出配音 JSON')).toBeTruthy(); expect(screen.getByText('导出配音 CSV')).toBeTruthy(); fireEvent.click(screen.getByText('生成全部可用配音')); }); });
