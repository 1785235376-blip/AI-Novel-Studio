import {BookOpen,Image,Video,Volume2,Plug,Workflow,FolderOpen} from 'lucide-react';
import type {ReactNode} from 'react';
export type StudioModule='NOVEL'|'IMAGE'|'VIDEO'|'ASSETS'|'AUDIO'|'PLUGIN'|'WORKFLOW';
export interface StudioModuleDefinition { id: StudioModule; label: string; icon: ReactNode; }
export const STUDIO_MODULES: StudioModuleDefinition[] = [
  {id:'NOVEL', icon:<BookOpen aria-hidden="true"/>, label:'小说'}, {id:'IMAGE', icon:<Image aria-hidden="true"/>, label:'图片'},
  {id:'VIDEO', icon:<Video aria-hidden="true"/>, label:'视频'}, {id:'ASSETS', icon:<FolderOpen aria-hidden="true"/>, label:'资产'},
  {id:'AUDIO', icon:<Volume2 aria-hidden="true"/>, label:'声音'}, {id:'PLUGIN', icon:<Plug aria-hidden="true"/>, label:'插件'},
  {id:'WORKFLOW', icon:<Workflow aria-hidden="true"/>, label:'工作流'},
];
