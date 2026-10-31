import {PipelineStatusPanel} from './PipelineStatusPanel';

/** The original screenplay pipeline owner supplies loading, error and review gates. */
export function ScreenplayPipelinePanel({novelId,screenplayId}:{novelId?:string;screenplayId?:string}){
  return <PipelineStatusPanel novelId={novelId} screenplayId={screenplayId}/>;
}
