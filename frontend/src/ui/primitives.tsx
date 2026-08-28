import {forwardRef} from 'react';
import type {ButtonHTMLAttributes,HTMLAttributes,ReactNode} from 'react';
type ButtonProps=ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'primary'|'secondary'|'ghost'|'danger';loading?:boolean};
export const Button=forwardRef<HTMLButtonElement,ButtonProps>(function Button({variant='secondary',loading=false,className='',children,...props},ref){return <button ref={ref} className={`ui-button ui-button--${variant} ${loading?'is-loading':''} ${className}`.trim()} aria-busy={loading||undefined} disabled={loading||props.disabled} {...props}>{loading&&<Spinner size="sm"/>}{children}</button>});
export function IconButton({label,className='',...props}:ButtonHTMLAttributes<HTMLButtonElement>&{label:string}){return <button className={`ui-icon-button ${className}`.trim()} aria-label={label} title={label} {...props}/>}
export function Badge({tone='neutral',children}:HTMLAttributes<HTMLSpanElement>&{tone?:'neutral'|'info'|'success'|'warning'|'error';children:ReactNode}){return <span className={`ui-badge ui-badge--${tone}`}>{children}</span>}
export type PanelProps=Omit<HTMLAttributes<HTMLElement>,'title'|'children'|'dangerouslySetInnerHTML'>&{title?:ReactNode;actions?:ReactNode;children:ReactNode};
export function Panel({title,actions,children,className='',...props}:PanelProps){return <section className={`ui-panel ${className}`.trim()} {...props}>{(title||actions)&&<header><h2>{title}</h2>{actions}</header>}{children}</section>}
export function EmptyState({title,detail}:{title:string;detail:string}){return <div className="ui-empty" role="status"><strong>{title}</strong><p>{detail}</p></div>}
export function Spinner({size='md'}:{size?:'sm'|'md'}){return <span className={`ui-spinner ui-spinner--${size}`} role="progressbar" aria-label="处理中"/>}
export function Tooltip({label,children}:{label:string;children:ReactNode}){return <span className="ui-tooltip"><span>{children}</span><span role="tooltip">{label}</span></span>}
export function Separator({orientation='horizontal'}:{orientation?:'horizontal'|'vertical'}){return <div className={`ui-separator ui-separator--${orientation}`} role="separator"/>}
export function StatusMessage({tone='info',children}:{tone?:'info'|'success'|'warning'|'error';children:ReactNode}){return <div className={`ui-status-message ui-status-message--${tone}`} role={tone==='error'?'alert':'status'}>{children}</div>}
