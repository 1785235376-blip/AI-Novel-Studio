import { useState } from "react";
import { AgentQueuePanel } from "../novel/AgentQueuePanel";
import { WorkflowInspector, type WorkflowInspection } from "../novel/WorkflowInspector";
import { WorkflowPanel } from "../novel/WorkflowPanel";
import { AppShell, type ScopeLabels, type StudioModule } from "./AppShell";

export function WorkflowWorkspaceRoute({ module, onModuleChange, scope, actor, novelId }: { module: StudioModule; onModuleChange: (module: StudioModule) => void; scope: ScopeLabels; actor: string; novelId: string }) {
  const [inspection, setInspection] = useState<WorkflowInspection>();
  return <AppShell module={module} onModuleChange={onModuleChange} scope={scope} actor={actor} sidebar={<></>} main={<><WorkflowPanel novelId={novelId} onInspect={setInspection}/><AgentQueuePanel novelId={novelId} onInspect={setInspection}/></>} inspector={<WorkflowInspector inspection={inspection} novelId={novelId}/>} status={<>工作流</>}/>;
}
