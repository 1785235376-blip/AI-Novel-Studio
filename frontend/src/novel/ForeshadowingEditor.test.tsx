// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ForeshadowingEditor} from './StoryDatabase';
afterEach(cleanup);

describe('ForeshadowingEditor',()=>{
  it('captures chapter targets and related entities',async()=>{
    const onSave=vi.fn();render(<ForeshadowingEditor characters={[{id:'lin-hai',name:'林海'}]} events={[{id:'port-lockdown',title:'雾港封锁'}]} onSave={onSave}/>);
    fireEvent.change(screen.getByLabelText('伏笔标题'),{target:{value:'破损罗盘'}});
    fireEvent.change(screen.getByLabelText('埋设章节'),{target:{value:'1'}});
    fireEvent.change(screen.getByLabelText('目标回收章节'),{target:{value:'8'}});
    const people=screen.getByLabelText('关联人物') as HTMLSelectElement;people.options[0].selected=true;fireEvent.change(people);
    const events=screen.getByLabelText('关联事件') as HTMLSelectElement;events.options[0].selected=true;fireEvent.change(events);
    fireEvent.click(screen.getByRole('button',{name:'保存伏笔'}));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({title:'破损罗盘',planted_chapter:1,target_chapter:8,characters:['lin-hai'],events:['port-lockdown']}));
  });
});
