// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DirectorWorkspace } from './DirectorWorkspace';
import { directorWorkspaceProjection } from './directorWorkspaceContract';
import { fixtureProjection } from './directorWorkspaceFixtures.testFixture';
import { cameraEvidence } from '../creative/cameraGeometry.testFixture';
import { createStudioGraphClient } from '../creative/studioGraphClient';
import { StudioGraphDirectorConsole } from '../creative/StudioGraphDirectorConsole';
afterEach(cleanup);
function projection() { const value = fixtureProjection(); value.document.mode = 'DIRECTOR'; value.camera_geometry = cameraEvidence(); return value; }
it('keeps legacy closed projections accepted and shows insufficient evidence without inventing coordinates', async () => {
  const value = fixtureProjection(); expect(directorWorkspaceProjection(value, 'doc-1')).not.toHaveProperty('camera_geometry');
  render(<DirectorWorkspace client={{ readDirectorWorkspace: vi.fn(async () => value) }} documentId="doc-1" />);
  const panel = await screen.findByLabelText('手填机位辅助证据'); expect(panel.textContent).toContain('信息不足'); expect(panel.textContent).toContain('主要决策依据');
  expect(within(panel).queryByRole('button')).toBeNull();
});
it('shows exact document pins, authored reasons and supplementary evidence in the original workspace', async () => {
  const value = projection(), evidence = value.camera_geometry!;
  evidence.findings[0].state = 'INTENTIONAL_OVERRIDE'; evidence.rows[1].camera_grammar!.intentional_axis_crossing = true;
  evidence.rows[1].camera_grammar!.override_reason = 'Deliberate spatial rupture';
  const decoded = directorWorkspaceProjection(value, 'doc-1'); expect(decoded.camera_geometry).toEqual(evidence);
  render(<DirectorWorkspace client={{ readDirectorWorkspace: vi.fn(async () => decoded) }} documentId="doc-1" />);
  const panel = await screen.findByLabelText('手填机位辅助证据');
  expect(panel.textContent).toContain('doc-1 · v3'); expect(panel.textContent).toContain('a'.repeat(64)); expect(panel.textContent).toContain('Deliberate spatial rupture');
  expect(panel.textContent).toContain('不是模型或画面分析'); expect(panel.textContent).toContain('note-1 → note-2');
});
it.each(['unknown', 'source-id', 'source-version', 'source-field', 'model-claim', 'visual-claim', 'row-id', 'pair', 'missing-finding', 'repeated-finding', 'unknown-state', 'bad-number', 'bad-geometry', 'fake-override'])(
  'rejects malformed or misbound supplementary evidence: %s', change => {
    const value: any = projection(), e = value.camera_geometry;
    if (change === 'unknown') e.execution = true;
    if (change === 'source-id') e.document_snapshot.id = 'other';
    if (change === 'source-version') e.document_snapshot.version++;
    if (change === 'source-field') e.source_field = 'shots';
    if (change === 'model-claim') e.model_called = true;
    if (change === 'visual-claim') e.visual_analysis = true;
    if (change === 'row-id') e.rows[1].id = e.rows[0].id;
    if (change === 'pair') e.findings[0].to_shot_id = 'foreign';
    if (change === 'missing-finding') e.findings.pop();
    if (change === 'repeated-finding') e.findings.push(e.findings[0]);
    if (change === 'unknown-state') e.findings[0].state = 'VISUALLY_VERIFIED';
    if (change === 'bad-number') e.findings[0].cross_products = ['NaN', '8'];
    if (change === 'bad-geometry') e.rows[0].camera_grammar.camera_position.x = '1';
    if (change === 'fake-override') e.findings[0].state = 'INTENTIONAL_OVERRIDE';
    expect(() => directorWorkspaceProjection(value, 'doc-1')).toThrow();
  });
it('leaves missing geometry insufficient while preserving unrelated row identity', () => {
  const value = projection(), e = value.camera_geometry!;
  e.rows[1].camera_grammar = null; e.rows[1].geometry_authored = false;
  e.findings[0] = { kind: 'AXIS', state: 'INSUFFICIENT_EVIDENCE', from_shot_id: 'note-1', to_shot_id: 'note-2', message: '信息不足' };
  expect(directorWorkspaceProjection(value, 'doc-1').camera_geometry).toEqual(e);
});
it('Graph Console requires the new evidence digest to match the original pinned owner snapshot', async () => {
  const value = projection(), pin = value.camera_geometry!.document_snapshot;
  value.camera_geometry!.document_snapshot = { ...pin, digest: 'b'.repeat(64) };
  const documents = { project_id: 'project-1', scope: { mode: 'local', novel_id: 'project-1' }, documents: [{ ...pin, mode: 'DIRECTOR', title: 'Direction' }] };
  const json = vi.fn().mockResolvedValueOnce(documents).mockResolvedValueOnce(value);
  await expect(createStudioGraphClient('project-1', {}, { json }).readDirectorWorkspace(pin)).rejects.toMatchObject({ status: 409 });
  expect(json).toHaveBeenCalledTimes(2);
});
it('the mounted Graph Console reuses supplementary findings and hides them for a stale node', async () => {
  const value = projection(), client = { readDirectorWorkspace: vi.fn(async () => value) };
  const props = { client, nodeId: 'director-node', identity: 'session-1', active: true, snapshot: value.camera_geometry!.document_snapshot,
    isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work() };
  const view = render(<StudioGraphDirectorConsole {...props} referenceState="CURRENT" />);
  expect(client.readDirectorWorkspace).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '展开导演控制台并核对来源' }));
  await screen.findByLabelText('手填机位辅助证据'); expect(screen.getByText('几何越轴提示')).toBeTruthy();
  view.rerender(<StudioGraphDirectorConsole {...props} referenceState="STALE" />);
  expect(screen.queryByLabelText('手填机位辅助证据')).toBeNull(); expect(client.readDirectorWorkspace).toHaveBeenCalledTimes(1);
});
it('clears source geometry when the original workspace authority/client changes', async () => {
  const value = projection(), first = { readDirectorWorkspace: vi.fn(async () => value) };
  const view = render(<DirectorWorkspace client={first} documentId="doc-1" />); await screen.findByText('几何越轴提示');
  const second = { readDirectorWorkspace: vi.fn(async () => { throw new Error('denied'); }) };
  view.rerender(<DirectorWorkspace client={second} documentId="doc-1" />);
  await waitFor(() => expect(screen.queryByText('几何越轴提示')).toBeNull());
});
