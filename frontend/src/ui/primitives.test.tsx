// @vitest-environment jsdom
import type {ComponentProps} from 'react';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {Panel} from './primitives';

type PublicPanelProps=ComponentProps<typeof Panel>;
const nativePropsCompileContract:PublicPanelProps={
  title:'Typed title',
  children:'Typed child',
  id:'typed-panel',
  role:'region',
  'aria-label':'Typed panel',
  'aria-describedby':'typed-description',
  tabIndex:0,
  style:{display:'block'},
  onClick:()=>undefined,
  onKeyDown:()=>undefined,
};
const dangerousPropsCompileContract:PublicPanelProps={
  children:'Child contract',
  // @ts-expect-error Panel owns children and excludes raw HTML injection.
  dangerouslySetInnerHTML:{__html:'unsafe'},
};
void nativePropsCompileContract;
void dangerousPropsCompileContract;

afterEach(cleanup);

describe('Panel native section props contract',()=>{
  it('renders the existing section, header, actions and children contract',()=>{
    render(<Panel title={<span>Panel title</span>} actions={<button>Panel action</button>}><p>Panel child</p></Panel>);
    const panel=screen.getByText('Panel child').closest('section');
    expect(panel?.tagName).toBe('SECTION');
    expect(panel?.className).toBe('ui-panel');
    expect(screen.getByRole('heading',{level:2,name:'Panel title'})).toBeTruthy();
    expect(screen.getByRole('button',{name:'Panel action'})).toBeTruthy();
    expect(panel?.hasAttribute('title')).toBe(false);
    expect(panel?.hasAttribute('actions')).toBe(false);
  });

  it('merges a custom class without losing or corrupting the base class',()=>{
    const {rerender}=render(<Panel className="custom-panel">Content</Panel>);
    expect(screen.getByText('Content').closest('section')?.className).toBe('ui-panel custom-panel');
    rerender(<Panel>Content</Panel>);
    expect(screen.getByText('Content').closest('section')?.className).toBe('ui-panel');
  });

  it('forwards standard identity, accessibility, data and focus attributes',()=>{
    render(<><p id="panel-description">Description</p><Panel id="panel-id" role="region" aria-label="Native panel" aria-describedby="panel-description" data-testid="native-panel" data-contract="forwarded" tabIndex={3}>Content</Panel></>);
    const panel=screen.getByTestId('native-panel');
    expect(panel.id).toBe('panel-id');
    expect(panel.getAttribute('role')).toBe('region');
    expect(panel.getAttribute('aria-label')).toBe('Native panel');
    expect(panel.getAttribute('aria-describedby')).toBe('panel-description');
    expect(panel.getAttribute('data-contract')).toBe('forwarded');
    expect(panel.tabIndex).toBe(3);
  });

  it('forwards style and invokes native event handlers exactly once',()=>{
    const click=vi.fn();
    const keyDown=vi.fn();
    render(<Panel aria-label="Interactive panel" style={{backgroundColor:'rgb(1, 2, 3)'}} onClick={click} onKeyDown={keyDown}>Interactive child</Panel>);
    const panel=screen.getByRole('region',{name:'Interactive panel'});
    expect((panel as HTMLElement).style.backgroundColor).toBe('rgb(1, 2, 3)');
    fireEvent.click(panel);
    fireEvent.keyDown(panel,{key:'Enter'});
    expect(click).toHaveBeenCalledTimes(1);
    expect(keyDown).toHaveBeenCalledTimes(1);
  });
});
