// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
const moduleState = vi.hoisted(() => ({ loaded: vi.fn(), render: vi.fn(), fail: false }));
vi.mock('./ExperimentalWorkbench', () => { moduleState.loaded(); return { ExperimentalWorkbench: (props: {novelId: string}) => { moduleState.render(props); if (moduleState.fail) throw new Error('synthetic tool load failure'); return <div>Loaded {props.novelId}</div>; } }; });
import { DeferredExperimentalWorkbench } from './DeferredExperimentalWorkbench';

afterEach(cleanup);
const flags = {experimental:true,default_enabled:false as const,features:{'experimental.workspace_tools_v2':true}};
describe('deferred experimental tools', () => {
  it('does not import the optional workbench until opened and preserves captured props', async () => {
    expect(moduleState.loaded).not.toHaveBeenCalled();
    const view = render(<><div>Editor remains active</div><DeferredExperimentalWorkbench novelId="off-project" context={{sessionToken:''}} /></>);
    expect(screen.getByText('Experimental 未启用')).toBeTruthy();
    expect(moduleState.loaded).not.toHaveBeenCalled();
    view.rerender(<><div>Editor remains active</div><DeferredExperimentalWorkbench novelId="captured-project" context={{sessionToken: ''}} flags={flags} /></>);
    expect(await screen.findByText('Loaded captured-project')).toBeTruthy();
    expect(screen.getByText('Editor remains active')).toBeTruthy();
    expect(moduleState.render.mock.lastCall?.[0].novelId).toBe('captured-project');
  });
  it('contains tool errors without replacing the editor and retries only the interface', async () => {
    const log=vi.spyOn(console,'error').mockImplementation(() => {}); moduleState.fail=true;
    try {
      const view=render(<><textarea aria-label="Draft" defaultValue="Unsaved sentence" /><DeferredExperimentalWorkbench novelId="other" context={{sessionToken: ''}} flags={flags} /></>);
      expect(await screen.findByLabelText('实验工具加载失败')).toBeTruthy();
      expect((screen.getByLabelText('Draft') as HTMLTextAreaElement).value).toBe('Unsaved sentence');
      moduleState.fail=false;
      await act(async () => { fireEvent.click(screen.getByRole('button',{name:'重试加载工具'})); });
      expect(await screen.findByText('Loaded other')).toBeTruthy();
      expect((screen.getByLabelText('Draft') as HTMLTextAreaElement).value).toBe('Unsaved sentence');view.unmount();
    } finally { moduleState.fail=false;log.mockRestore(); }
  });
});
