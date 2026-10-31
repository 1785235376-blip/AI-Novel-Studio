// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { changeVisualMembership } from './graphVisualMembership';
import { GraphVisualGroups } from './GraphVisualGroups';
import type { StudioGraphDefinition } from './studioGraphTypes';
const graph = (): StudioGraphDefinition => ({ schema_version: 1, title: 'Membership',
  nodes: ['a','b','c','d'].map((id,i) => ({ id, definition_id: 'text_input', definition_version: 1, enabled: true,
    position: {x: i*300,y: 0}, parameters: {text:id} })), edges: [], viewport: {x:0,y:0,zoom:1},
  presentation: {comment:'Keep', groups:[{id:'parent',name:'Parent',node_ids:['a']},
    {id:'child',name:'Child',node_ids:['b'],parent_id:'parent'}, {id:'target',name:'Target',node_ids:['c']}]},
});
afterEach(cleanup);
it('transfers membership exclusively and promotes child when emptied parent disappears', () => {
  const source = graph(), original = JSON.stringify(source);
  expect(changeVisualMembership(source,['a','d'],'target','move')).toEqual([
    {id:'child',name:'Child',node_ids:['b']},{id:'target',name:'Target',node_ids:['c','a','d']},
  ]);
  expect(JSON.stringify(source)).toBe(original);
});
it('removes only selected direct members and never deletes child nodes', () => {
  const source = graph();
  expect(changeVisualMembership(source,['a','b'],'parent','remove')).toEqual([
    {id:'child',name:'Child',node_ids:['b']},{id:'target',name:'Target',node_ids:['c']},
  ]);
  expect(changeVisualMembership(source,['b'],'parent','remove')).toBeNull();
});
it('refuses unknown, duplicate, empty and no-op selections and overflow', () => {
  const source=graph();
  for(const ids of [[],['missing'],['a','a'],['c']]) expect(changeVisualMembership(source,ids,'target','move')).toBeNull();
  expect(changeVisualMembership(source,['a'],'missing','move')).toBeNull();
  const large=graph(); large.nodes=Array.from({length:25},(_,i)=>({...large.nodes[0],id:`n${i}`}));
  large.presentation!.groups=[{id:'g',name:'G',node_ids:large.nodes.slice(0,24).map(n=>n.id)}];
  expect(changeVisualMembership(large,['n24'],'g','move')).toBeNull();
});
it('emits one original graph history edit, preserving nodes, edges, viewport and annotations', () => {
  const definition=graph(), change=vi.fn();
  render(<GraphVisualGroups definition={definition} selected={['a','d']} blocked={false} interactionKey="p1" onChange={change} onSelect={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('视觉分组'),{target:{value:'target'}});
  const button=screen.getByRole('button',{name:'将所选节点移入当前组'});
  fireEvent.click(button); fireEvent.click(button);
  expect(change).toHaveBeenCalledTimes(1);
  const [next,record]=change.mock.calls[0];
  expect(record).toBe(true); expect(next.nodes).toBe(definition.nodes); expect(next.edges).toBe(definition.edges);
  expect(next.viewport).toBe(definition.viewport); expect(next.presentation.comment).toBe('Keep');
  expect(next.presentation.groups).toEqual(changeVisualMembership(definition,['a','d'],'target','move'));
});
it('rejects retained mutation callbacks after owner transition or unmount', () => {
  const definition=graph(), change=vi.fn();
  const props={definition,selected:['a'],blocked:false,onChange:change,onSelect:vi.fn()};
  const view=render(<GraphVisualGroups {...props} interactionKey="p1" />);
  fireEvent.change(screen.getByLabelText('视觉分组'),{target:{value:'target'}});
  const button=screen.getByRole('button',{name:'将所选节点移入当前组'});
  const key=Object.keys(button).find(k=>k.startsWith('__reactProps$'))!;
  const retained=(button as unknown as Record<string,{onClick:()=>void}>)[key].onClick;
  view.rerender(<GraphVisualGroups {...props} interactionKey="p2" blocked />);
  retained(); expect(change).not.toHaveBeenCalled();
  view.unmount(); retained(); expect(change).not.toHaveBeenCalled();
});
