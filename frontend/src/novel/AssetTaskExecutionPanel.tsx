import {useMutation,useQueryClient} from '@tanstack/react-query';
import {api} from '../api';
import {Badge,Button} from '../ui/primitives';

export function AssetTaskExecutionPanel({novelId,screenplayId,tasks}:{novelId:string;screenplayId:string;tasks:any[]}){
  const qc=useQueryClient();
  const execute=useMutation({mutationFn:(id:string)=>api.executeAssetTask(novelId,screenplayId,id),onSuccess:()=>void qc.invalidateQueries({queryKey:['screenplays',novelId]})});
  return <section className="novel-draft-review"><h4>生成任务执行</h4>{tasks.map(task=><article key={task.id}><header><strong>{task.model_id||'未选择模型'}</strong><Badge>{task.status}</Badge></header>{task.asset_uri&&<p className="novel-help">结果：{task.asset_uri}</p>}{task.error&&<p className="novel-help">错误：{task.error}</p>}{task.status==='RUNNING'&&<Button disabled={execute.isPending} onClick={()=>execute.mutate(task.id)}>执行任务</Button>}</article>)}</section>;
}
