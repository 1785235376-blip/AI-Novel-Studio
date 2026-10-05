import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {ExportPanel} from '../../src/novel/ExportPanel';
import {setCollaborationContext} from '../../src/api';
import '../../src/ui/tokens.css';
import '../../src/ui/ui.css';
const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
function Fixture(){
  const [actor,setActor]=useState('session-owner');
  const [branch,setBranch]=useState('branch-a');
  const scope={workspaceId:'synthetic-workspace',projectId:'synthetic-project',storylineId:'synthetic-story',branchId:branch};
  setCollaborationContext({sessionToken:actor,scope});
  return <QueryClientProvider client={client}><main><label>测试身份<select aria-label="测试身份" value={actor} onChange={event=>setActor(event.target.value)}><option value="session-owner">任务所有者</option><option value="session-other">其他用户</option></select></label><label>测试分支<select aria-label="测试分支" value={branch} onChange={event=>setBranch(event.target.value)}><option>branch-a</option><option>branch-b</option></select></label><ExportPanel novelId="synthetic-project" scope={scope} sessionToken={actor}/></main></QueryClientProvider>;
}
createRoot(document.getElementById('root')!).render(<Fixture/>);
