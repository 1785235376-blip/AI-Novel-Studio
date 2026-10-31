// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY PARAMS] Editable ComfyUI-style widget values persist with the draft.
import {afterEach, beforeEach, describe, expect, it} from 'vitest';
import {cleanup, fireEvent, render, waitFor, within} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {sessionCanvasStore} from '../RebuildCanvas';
import {useStudio} from '../../../store';

const layer = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const widget = (name: string) => layer().querySelector(`[data-comfy-params] [data-widget-name="${name}"]`) as HTMLInputElement;
const openMenuAndAdd = async (type: string) => {
  fireEvent.contextMenu(within(layer()).getByRole('application'), {clientX: 40, clientY: 40});
  const option = await waitFor(() => {
    const found = layer().querySelector(`[data-add-node-menu] [data-node-type="${type}"]`);
    expect(found).toBeTruthy();
    return found as HTMLElement;
  });
  fireEvent.click(option);
};

beforeEach(() => {
  cleanup(); localStorage.clear(); sessionCanvasStore.clear();
  useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined, sessionToken: ''});
});
afterEach(() => { cleanup(); sessionCanvasStore.clear(); useStudio.setState({actor: undefined, scope: undefined, sessionToken: ''}); });

describe('ComfyCanvas widget parameters', () => {
  it('shows editable parameters for the selected node and persists values with the draft', async () => {
    const view = render(<DualStack kind="image" scope="n1" />);
    await openMenuAndAdd('KSampler');
    await waitFor(() => expect(layer().querySelector('[data-comfy-params]')).toBeTruthy());
    expect(widget('seed')).toBeTruthy();
    expect(widget('steps')).toBeTruthy();
    expect(widget('cfg')).toBeTruthy();

    fireEvent.change(widget('seed'), {target: {value: '123'}});
    fireEvent.change(widget('steps'), {target: {value: '25'}});
    fireEvent.change(widget('cfg'), {target: {value: '7.5'}});
    expect(widget('seed').value).toBe('123');
    expect(widget('steps').value).toBe('25');
    expect(widget('cfg').value).toBe('7.5');

    // Unmount/remount: the same session draft carries the edited widget values, not only nodes/edges.
    view.unmount();
    render(<DualStack kind="image" scope="n1" />);
    const node = await waitFor(() => {
      const found = layer().querySelector('[data-node-id]');
      expect(found).toBeTruthy();
      return found as HTMLElement;
    });
    fireEvent.pointerDown(node, {clientX: 10, clientY: 10, pointerId: 1});
    await waitFor(() => expect(layer().querySelector('[data-comfy-params]')).toBeTruthy());
    expect(widget('seed').value).toBe('123');
    expect(widget('steps').value).toBe('25');
    expect(widget('cfg').value).toBe('7.5');
  });

  it('does not commit an empty/invalid number and keeps boolean/string widgets editable', async () => {
    render(<DualStack kind="image" scope="n1" />);
    await openMenuAndAdd('KSamplerAdvanced');
    await waitFor(() => expect(layer().querySelector('[data-comfy-params]')).toBeTruthy());
    const noise = widget('noise_seed');
    fireEvent.change(noise, {target: {value: '5'}});
    expect(noise.value).toBe('5');
    fireEvent.change(noise, {target: {value: ''}});
    expect(noise.value).toBe('5'); // empty input is ignored, not committed as NaN/0

    fireEvent.change(layer().querySelector('[data-widget-name="add_noise"]')!, {target: {value: 'disable'}});
    expect((layer().querySelector('[data-widget-name="add_noise"]') as HTMLSelectElement).value).toBe('disable');
    expect((layer().querySelector('[data-widget-name="sampler_name"]') as HTMLInputElement)).toBeTruthy();
  });
});
