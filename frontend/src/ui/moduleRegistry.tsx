import {BookOpen,Image,Video,Volume2,Scissors,FolderOpen,Plug,Workflow,BrainCircuit} from 'lucide-react';
import type {ReactNode} from 'react';
/** Full module id union (routes + deep links). Chrome shows only STUDIO_MODULES (6). */
export type StudioModule='NOVEL'|'IMAGE'|'VIDEO'|'AUDIO'|'EDIT'|'ASSETS'|'CONTROL'|'PLUGIN'|'WORKFLOW';
export interface StudioModuleDefinition { id: StudioModule; label: string; icon: ReactNode; }
/**
 * [HERMIA-FE-20261022] Default ModuleSwitcher chrome = 6 buttons (Lumen W-P0 / user confirm):
 * NOVEL→IMAGE→VIDEO→AUDIO→EDIT(剪辑)→ASSETS.
 * CONTROL/PLUGIN/WORKFLOW stay typed + command-reachable; NOT default chrome (LUMEN_WORKSPACE_ARCH §4).
 * VIDEO ≠ EDIT (LUMEN_VIDEO_IA): video = script/canvas/director; EDIT = NLE.
 */
export const STUDIO_MODULES: StudioModuleDefinition[] = [
  {id:'NOVEL', icon:<BookOpen aria-hidden="true"/>, label:'小说'},
  {id:'IMAGE', icon:<Image aria-hidden="true"/>, label:'图片'},
  {id:'VIDEO', icon:<Video aria-hidden="true"/>, label:'视频'},
  {id:'AUDIO', icon:<Volume2 aria-hidden="true"/>, label:'声音'},
  {id:'EDIT', icon:<Scissors aria-hidden="true"/>, label:'剪辑'},
  {id:'ASSETS', icon:<FolderOpen aria-hidden="true"/>, label:'资产'},
];
/** Discoverable outside default chrome (设置 / 命令 / 专业「更多」深链). */
export const STUDIO_MODULE_OVERFLOW: StudioModuleDefinition[] = [
  {id:'CONTROL', icon:<BrainCircuit aria-hidden="true"/>, label:'主控'},
  {id:'PLUGIN', icon:<Plug aria-hidden="true"/>, label:'插件'},
  {id:'WORKFLOW', icon:<Workflow aria-hidden="true"/>, label:'工作流'},
];
export const ALL_STUDIO_MODULES: StudioModuleDefinition[] = [...STUDIO_MODULES, ...STUDIO_MODULE_OVERFLOW];
