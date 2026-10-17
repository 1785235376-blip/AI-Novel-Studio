import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync, spawnSync} from 'node:child_process';
const root='/workspace/scratch/20a0022d2b33/studio-storyboard-handoff';
const prefix='/tmp/dot-storyboard-independent-20261017';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const snapshot=()=>Object.fromEntries([...new Set(execFileSync('git',['ls-files','--cached','--others','--exclude-standard','frontend'],{cwd:root,encoding:'utf8'}).trim().split('\n'))].sort().filter(p=>p&&fs.lstatSync(path.join(root,p)).isFile()).map(p=>[p,sha(fs.readFileSync(path.join(root,p)))]));
const before=snapshot();fs.writeFileSync(prefix+'-before.json',JSON.stringify(before,null,2)+'\n');
const files=['src/creative/StoryboardImageHandoff.additive.test.tsx','src/creative/IndependentStudioStoryboardHandoff.additive.test.tsx','src/creative/StudioStoryboardAssetHandoff.additive.test.tsx','src/creative/StoryboardProductionPanel.phase4.test.tsx','src/creative/IndependentStudioWorkspace.navigation.additive.test.tsx','src/creative/IndependentStudioWorkspace.test.tsx'];
const args=['node_modules/vitest/vitest.mjs','run',...files,'--maxWorkers=1','--minWorkers=1','--no-file-parallelism','--no-cache'];
const started=new Date().toISOString();const fd=fs.openSync(prefix+'.log','w');
const result=spawnSync(process.execPath,args,{cwd:path.join(root,'frontend'),stdio:['ignore',fd,fd]});fs.closeSync(fd);
const followups=[];
if(result.status===0) {
 for(const [name,cwd,cmdArgs] of [
 ['typecheck',path.join(root,'frontend'),['node_modules/typescript/bin/tsc','-b','--force','--pretty','false']],
 ['build',path.join(root,'frontend'),['node_modules/vite/bin/vite.js','build']],
 ['tokens-global',root,['scripts/check_ui_design_tokens.mjs']]]) {
  const start=new Date().toISOString(), logfile=prefix+'-'+name+'.log', f=fs.openSync(logfile,'w');
  const r=spawnSync(process.execPath,cmdArgs,{cwd,stdio:['ignore',f,f]});fs.closeSync(f);
  followups.push({name,command:[process.execPath,...cmdArgs],cwd,started_utc:start,finished_utc:new Date().toISOString(),exit_code:r.status,signal:r.signal,logfile,log_sha256:sha(fs.readFileSync(logfile))});
  if(r.status!==0) break;
 }
}
const runtimeFiles=['StudioStoryboardAssetHandoff.tsx','useStoryboardProductionController.ts','StoryboardProductionPanel.tsx','IndependentStudioWorkspace.tsx'].map(p=>'frontend/src/creative/'+p);
const rawColorFindings=runtimeFiles.flatMap(p=>fs.readFileSync(path.join(root,p),'utf8').split('\n').flatMap((line,i)=>/#[0-9a-f]{3,8}\b|\brgb\(|\bhsl\(/i.test(line)?[{path:p,line:i+1,text:line}]:[]));
fs.writeFileSync(prefix+'-tokens-scoped.json',JSON.stringify({runtimeFiles,rawColorFindings},null,2)+'\n');
const after=snapshot();fs.writeFileSync(prefix+'-after.json',JSON.stringify(after,null,2)+'\n');
const changed=[...new Set([...Object.keys(before),...Object.keys(after)])].filter(p=>before[p]!==after[p]);
const log=fs.readFileSync(prefix+'.log');
const report={schema_version:1,base_commit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),worktree:root,started_utc:started,finished_utc:new Date().toISOString(),command:[process.execPath,...args],working_directory:'frontend',exit_code:result.status,signal:result.signal,error:result.error?.message,policy:'One worker, default timeouts, cache disabled. Controlled frontend only.',followups,rawColorFindings,source_count:Object.keys(before).length,changed_sources:changed,sources_changed:changed.length>0,before_sha256:sha(fs.readFileSync(prefix+'-before.json')),after_sha256:sha(fs.readFileSync(prefix+'-after.json')),log_sha256:sha(log),test_summary:log.toString().split('\n').filter(line=>/Test Files|Tests\s|Duration/.test(line))};
fs.writeFileSync(prefix+'.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));process.exit(result.status|| (changed.length||followups.some(x=>x.exit_code!==0)||rawColorFindings.length?1:0));
