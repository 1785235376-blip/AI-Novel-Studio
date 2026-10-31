// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { ExecutionImpactPanel } from './ExecutionImpactPanel';
import { impactInput } from './executionImpact.testFixtures';
import type { ExecutionImpactConfirmation } from './executionImpact';

beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { cleanup();vi.unstubAllGlobals(); });
function setup(isCurrent = () => true) {
  const props = { input: impactInput(), owner: {}, current: true, canConfirm: true, isCurrent, onConfirm: vi.fn() };
  return { ...render(<ExecutionImpactPanel {...props}/>), props };
}
async function issue(f: ReturnType<typeof setup>) {
  const checkbox = screen.getByLabelText('已核对本次输入变化与影响范围') as HTMLInputElement;
  await waitFor(() => expect(checkbox.disabled).toBe(false));
  fireEvent.click(checkbox);fireEvent.click(screen.getByRole('button', {name: '确认本次输入核对'}));
  return f.props.onConfirm.mock.calls.at(-1)![0] as ExecutionImpactConfirmation;
}
it('keeps an unchanged legal confirmation valid across repeated boundary checks', async () => {
  const f = setup(), proof = await issue(f);
  for (let i = 0; i < 3; i++) expect(proof.isCurrent()).toBe(true);
  expect(f.props.onConfirm).toHaveBeenCalledTimes(1);
});
it('permanently retires observed in-place A/B/A and requires explicit confirmation in a fresh owner generation', async () => {
  const f = setup(), old = await issue(f), prompt = f.props.input.command.prompt;
  f.props.input.command.prompt = 'Synthetic unrendered B';expect(old.isCurrent()).toBe(false);
  f.props.input.command.prompt = prompt;expect(old.isCurrent()).toBe(false);expect(old.isCurrent()).toBe(false);
  // Only after proving no-render retirement, start a fresh legitimate owner generation.
  f.rerender(<ExecutionImpactPanel {...f.props} owner={{}}/>);
  expect((screen.getByLabelText('已核对本次输入变化与影响范围') as HTMLInputElement).checked).toBe(false);
  const fresh = await issue(f);expect(fresh.isCurrent()).toBe(true);expect(old.isCurrent()).toBe(false);
  expect(f.props.onConfirm).toHaveBeenCalledTimes(2);
});
it.each(['false', 'throw'])('permanently retires an observed %s owner guard even if it becomes true without render', async kind => {
  let valid = true;
  const f = setup(() => { if (!valid && kind === 'throw') throw new Error('Synthetic retired guard');return valid; });
  const proof = await issue(f);expect(proof.isCurrent()).toBe(true);valid = false;expect(proof.isCurrent()).toBe(false);
  valid = true;expect(proof.isCurrent()).toBe(false);expect(f.props.onConfirm).toHaveBeenCalledTimes(1);
});
