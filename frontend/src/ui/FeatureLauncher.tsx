import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import type {KeyboardEvent as ReactKeyboardEvent,ReactNode} from 'react';
import {Activity,BookMarked,BookOpen,ChevronDown,ChevronUp,ClipboardList,Download,FileInput,Film,FolderOpen,History,LayoutDashboard,Map,Menu,PenLine,ScanSearch,ScrollText,Settings2,Shield,Users,UsersRound,WandSparkles,Workflow} from 'lucide-react';
import {Badge,Button,Tooltip} from './primitives';

export interface FeatureItemDefinition {
  id:string;
  label:string;
  icon:ReactNode;
}

export interface FeatureGroupDefinition {
  id:string;
  label:string;
  icon:ReactNode;
  items:readonly FeatureItemDefinition[];
}

/**
 * The feature IDs are part of the existing panel contract. Keep them stable:
 * App.tsx and its domain panels use these values to select the active surface.
 */
export const FEATURE_GROUPS:readonly FeatureGroupDefinition[]=[
  {id:'create',label:'创作',icon:<PenLine aria-hidden="true"/>,items:[
    {id:'story',label:'故事资料库',icon:<BookOpen aria-hidden="true"/>},
    {id:'overview',label:'概览',icon:<LayoutDashboard aria-hidden="true"/>},
    {id:'history',label:'版本历史',icon:<History aria-hidden="true"/>},
    {id:'workflow',label:'AI 写作流程',icon:<Workflow aria-hidden="true"/>},
  ]},
  {id:'production',label:'制作与分析',icon:<Film aria-hidden="true"/>,items:[
    {id:'check',label:'一致性检查',icon:<ScanSearch aria-hidden="true"/>},
    {id:'adaptation',label:'智能改编',icon:<WandSparkles aria-hidden="true"/>},
    {id:'screenplay',label:'影视剧本',icon:<Film aria-hidden="true"/>},
    {id:'assets',label:'资产库',icon:<FolderOpen aria-hidden="true"/>},
    {id:'exports',label:'导出中心',icon:<Download aria-hidden="true"/>},
    {id:'knowledge',label:'导入与知识审核',icon:<FileInput aria-hidden="true"/>},
    {id:'research',label:'研究资料',icon:<BookMarked aria-hidden="true"/>},
  ]},
  {id:'collaboration',label:'协作',icon:<UsersRound aria-hidden="true"/>,items:[
    {id:'agents',label:'Agent 团队',icon:<Users aria-hidden="true"/>},
    {id:'members',label:'团队成员',icon:<UsersRound aria-hidden="true"/>},
    {id:'permissions',label:'权限设置',icon:<Shield aria-hidden="true"/>},
  ]},
  {id:'system',label:'系统',icon:<Settings2 aria-hidden="true"/>,items:[
    {id:'diagnostics',label:'模型状态',icon:<Activity aria-hidden="true"/>},
    {id:'settings',label:'设置',icon:<Settings2 aria-hidden="true"/>},
    {id:'roadmap',label:'能力路线图',icon:<Map aria-hidden="true"/>},
    {id:'audit',label:'操作记录',icon:<ClipboardList aria-hidden="true"/>},
    {id:'snapshots',label:'写作上下文',icon:<ScrollText aria-hidden="true"/>},
  ]},
];

export const FEATURE_GROUP_DEFAULTS:Record<string,boolean>={create:true,production:true,collaboration:false,system:false};

interface FeatureLauncherProps {
  selectedId:string;
  expandedGroups:Readonly<Record<string,boolean>>;
  onSelect:(id:string)=>void;
  onToggleGroup:(id:string)=>void;
}

function focusableElements(root:HTMLElement|null){
  return root
    ? [...root.querySelectorAll<HTMLButtonElement>('[data-feature-focusable="true"]:not([disabled])')]
    : [];
}

export function FeatureLauncher({selectedId,expandedGroups,onSelect,onToggleGroup}:FeatureLauncherProps){
  const [open,setOpen]=useState(false);
  const launcherRef=useRef<HTMLDivElement>(null);
  const overlayRef=useRef<HTMLElement>(null);
  const toggleRef=useRef<HTMLButtonElement>(null);
  const wasOpen=useRef(false);
  const activeGroup=FEATURE_GROUPS.find(group=>group.items.some(item=>item.id===selectedId));
  const activeItem=activeGroup?.items.find(item=>item.id===selectedId);

  const openLauncher=()=>{
    // Keep the selected feature reachable when its group was collapsed in the
    // previous session. The group state remains persisted by the parent.
    if(activeGroup&&!expandedGroups[activeGroup.id]) onToggleGroup(activeGroup.id);
    setOpen(true);
  };
  const closeLauncher=()=>setOpen(false);

  useLayoutEffect(()=>{
    if(open){
      const target=overlayRef.current?.querySelector<HTMLButtonElement>(`[data-feature-id="${selectedId}"]`)
        ?? overlayRef.current?.querySelector<HTMLButtonElement>('[data-feature-item="true"]')
        ?? overlayRef.current?.querySelector<HTMLButtonElement>('[data-feature-focusable="true"]');
      target?.focus();
      wasOpen.current=true;
    }else if(wasOpen.current){
      wasOpen.current=false;
      toggleRef.current?.focus();
    }
  },[open,selectedId]);

  useEffect(()=>{
    if(!open)return;
    const onPointerDown=(event:PointerEvent)=>{
      if(!launcherRef.current?.contains(event.target as Node)) closeLauncher();
    };
    const onKeyDown=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){
        event.preventDefault();
        event.stopPropagation();
        closeLauncher();
      }
    };
    document.addEventListener('pointerdown',onPointerDown);
    document.addEventListener('keydown',onKeyDown);
    return()=>{
      document.removeEventListener('pointerdown',onPointerDown);
      document.removeEventListener('keydown',onKeyDown);
    };
  },[open]);

  const handleOverlayKeyDown=(event:ReactKeyboardEvent<HTMLElement>)=>{
    const buttons=focusableElements(overlayRef.current);
    const current=document.activeElement as HTMLButtonElement|null;
    const index=current?buttons.indexOf(current):-1;
    if(event.key==='Tab'){
      if(!buttons.length)return;
      event.preventDefault();
      buttons[(index+(event.shiftKey?-1:1)+buttons.length)%buttons.length]?.focus();
    }else if(event.key==='ArrowDown'||event.key==='ArrowRight'||event.key==='ArrowUp'||event.key==='ArrowLeft'||event.key==='Home'||event.key==='End'){
      if(!buttons.length)return;
      event.preventDefault();
      const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:Math.max(0,(index+(event.key==='ArrowDown'||event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length);
      buttons[next]?.focus();
    }
  };

  return <div className="feature-launcher" ref={launcherRef}>
    <Tooltip label={open?'关闭功能导航':'打开功能导航'}>
      <Button
        ref={toggleRef}
        type="button"
        variant="ghost"
        className="feature-launcher__toggle"
        aria-label={open?'关闭功能导航':'打开功能导航'}
        aria-expanded={open}
        aria-controls="feature-launcher-overlay"
        onClick={()=>open?closeLauncher():openLauncher()}
      >
        <Menu aria-hidden="true"/><span>功能导航</span>{open?<ChevronDown aria-hidden="true"/>:<ChevronUp aria-hidden="true"/>}
      </Button>
    </Tooltip>
    {open&&<nav
      id="feature-launcher-overlay"
      ref={overlayRef}
      className="feature-launcher__overlay"
      aria-label="功能面板导航"
      onKeyDown={handleOverlayKeyDown}
    >
      <header className="feature-launcher__header">
        <strong>功能面板</strong>
        <span>{activeItem?`当前：${activeItem.label}`:'选择一个功能'}</span>
      </header>
      <div className="feature-launcher__scroll">
        {FEATURE_GROUPS.map(group=>{
          const expanded=!!expandedGroups[group.id];
          const active=activeGroup?.id===group.id;
          const groupItemsId=`feature-group-items-${group.id}`;
          return <section className={`feature-group${active?' is-active':''}`} key={group.id}>
            <button
              type="button"
              className="feature-group__header"
              aria-expanded={expanded}
              aria-controls={expanded?groupItemsId:undefined}
              data-feature-focusable="true"
              onClick={()=>onToggleGroup(group.id)}
            >
              <span className="feature-group__label">{group.icon}<span>{group.label}</span></span>
              {active&&<Badge tone="info">当前</Badge>}
              {expanded?<ChevronDown aria-hidden="true"/>:<ChevronUp aria-hidden="true"/>}
            </button>
            {expanded&&<div id={groupItemsId} className="feature-group__items">
              {group.items.map(item=><button
                type="button"
                key={item.id}
                className={`feature-item${selectedId===item.id?' is-active':''}`}
                aria-current={selectedId===item.id?'page':undefined}
                data-feature-item="true"
                data-feature-id={item.id}
                data-feature-focusable="true"
                onClick={()=>onSelect(item.id)}
              >{item.icon}<span>{item.label}</span></button>)}
            </div>}
          </section>;
        })}
      </div>
    </nav>}
  </div>;
}
