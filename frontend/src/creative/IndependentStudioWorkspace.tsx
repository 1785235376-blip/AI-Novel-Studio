import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, apiErrorView, type Asset, type CollaborationContext } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { AppShell, type ScopeLabels, type StudioModule } from '../ui/AppShell';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { AssetLibraryPanel, type AssetLibraryAdapter } from '../novel/AssetLibraryPanel';
import { AssetInspector } from '../novel/AssetInspector';
import { AssetLineageForm, type LineageAsset } from '../experimental/ProductionLineagePanel';
import { studioClient, type CreativeIntent, type StudioAsset, type StudioOverview, type StudioPreferences, type StudioStorage, type WorkspacePreset } from './studioClient';
import { rememberLocalStudioSelection, rememberLocalWorkspaceSelection, type LocalStudioModule } from '../workspaceSelection';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import './independentStudio.css';

const intents: [CreativeIntent, string][] = [['NOVEL_WRITING', '小说创作'], ['NOVEL_ADAPTATION', '小说改编'], ['AI_SHORT_FILM', '短片'], ['COMMERCIAL_CG', '商业 CG'], ['ADVERTISEMENT', '广告'], ['MUSIC_VIDEO', 'MV'], ['GAME_PREVIS', '游戏预演'], ['IMAGE_DESIGN', '图片设计'], ['PODCAST_VOICE', '播客 / 配音'], ['BLANK', '空白创作'], ['CUSTOM', '自定义']];
const presets: [WorkspacePreset, string][] = [['BLANK', '空白'], ['TEXT', '文本'], ['IMAGE', '图片'], ['VIDEO', '视频'], ['AUDIO', '声音'], ['EDITING', '剪辑'], ['MIXED', '混合']];
export const isManualStudioModule = (module: StudioModule): module is LocalStudioModule => ['IMAGE', 'ASSETS', 'VIDEO', 'AUDIO'].includes(module);
let studioObserver = 0;
const signature = (projectId: string, context: CollaborationContext) => JSON.stringify([projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
function lineageAsset(asset: Asset): LineageAsset {
  const row = asset.provenance;
  return { id: asset.id, label: asset.filename, kind: asset.kind, version: asset.version!, digest: asset.sha256, deleted: !!asset.deleted_at,
    integrity: row?.integrity || 'CONTENT_UNAVAILABLE', origin: row?.origin || 'UNDECLARED', license: row?.license || { label: 'UNSPECIFIED', source: '', note: '' },
    operation: row?.operation || '', parents: row?.parents || [], sources: row?.sources || [], stale: row?.stale ?? true };
}
export type IndependentStudioProps = { projectId: string; context: CollaborationContext; scope: ScopeLabels; actor: string; module: LocalStudioModule;
  requestedAssetId?: string; onModuleChange: (module: StudioModule) => void; onProjectChoice: () => void; onVerified?: (projectId: string) => void; status?: ReactNode };

/** Independent module content; the original shell and asset owners remain authoritative. */
export function IndependentStudioWorkspace(props: IndependentStudioProps) {
  return <IndependentStudioSession key={signature(props.projectId, props.context)} {...props} />;
}
function IndependentStudioSession({ projectId, context, scope, actor, module, requestedAssetId, onModuleChange, onProjectChoice, onVerified, status }: IndependentStudioProps) {
  const query = useQueryClient();
  const hostToken = useLocalHostSession(state => state.token);
  const capturedToken = useRef(hostToken);
  const watchHost = !context.sessionToken && !context.scope && !context.actor;
  const origin = useRef(signature(projectId, context));
  const alive = useRef(true), revoked = useRef(false), busyRef = useRef(false);
  const client = useMemo(() => studioClient(projectId, context), [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const [cacheKey] = useState(() => `independent-studio-${++studioObserver}`);
  const [overview, setOverview] = useState<StudioOverview>(), [preferences, setPreferences] = useState<StudioPreferences>(), [rows, setRows] = useState<StudioAsset[]>([]);
  const [selected, setSelected] = useState<Asset>(), [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false), [busy, setBusy] = useState(false), [readingAsset, setReadingAsset] = useState(false), [storageLoading, setStorageLoading] = useState(false);
  const [pendingDeclaration, setPendingDeclaration] = useState<StudioAsset>(), [lineageDirty, setLineageDirty] = useState(false), [relationshipDirty, setRelationshipDirty] = useState(false), [formRevision, setFormRevision] = useState(0), [storage, setStorage] = useState<StudioStorage>();
  const [pendingNavigation, setPendingNavigation] = useState<() => void>(), [discard, setDiscard] = useState(false);
  const selectionEpoch = useRef(0), storageReading = useRef(false);
  const lastImport = useRef<{ body: string; key: string }>();
  const current = useCallback(() => {
    const state = useStudio.getState();
    return alive.current && !revoked.current && (!watchHost || capturedToken.current === useLocalHostSession.getState().token)
      && origin.current === signature(state.novelId, { sessionToken: state.sessionToken, actor: state.actor, scope: state.scope });
  }, [watchHost]);
  const deny = useCallback(() => { revoked.current = true; setDenied(true); setSelected(undefined); setRows([]); setOverview(undefined); setPreferences(undefined); setStorage(undefined); setPendingDeclaration(undefined); setLineageDirty(false); setRelationshipDirty(false); }, []);
  const guarded = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
    if (!current()) throw new Error('项目或会话已改变，请重新打开。');
    try { const result = await operation(); if (!current()) throw new Error('项目或会话已改变，请重新打开。'); return result; }
    catch (reason) { if (alive.current && reason instanceof ApiError && [401, 403].includes(reason.status)) deny(); throw reason; }
  }, [current, deny]);
  const writable = overview?.capabilities.can_mutate === true && !denied;
  const preferenceDirty = !!preferences && !!overview && JSON.stringify(preferences) !== JSON.stringify(overview.preferences);
  const dirty = preferenceDirty || lineageDirty || relationshipDirty;
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const lineageDirtyRef = useRef(lineageDirty); lineageDirtyRef.current = lineageDirty;
  const relationshipDirtyRef = useRef(relationshipDirty); relationshipDirtyRef.current = relationshipDirty;
  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const value = await guarded(() => client.overview());
      if (value.project.id !== projectId || value.project.entry_kind !== 'NEUTRAL_STUDIO') throw new Error('当前项目尚未启用独立工作区，请返回项目列表重新选择。');
      if (!value.capabilities || !value.preferences || !Number.isSafeInteger(value.preferences.version) || !Array.isArray(value.preferences.intents)) throw new Error('项目能力或偏好数据不可用，请重新读取。');
      setOverview(value); setPreferences(value.preferences); onVerified?.(projectId);
    } catch (reason) { if (alive.current) setError(apiErrorView(reason, '项目读取失败。').message); }
    finally { if (alive.current) setLoading(false); }
  }, [client, guarded, onVerified, projectId]);
  useEffect(() => { alive.current = true; void refresh(); return () => { alive.current = false; }; }, [refresh]);
  useEffect(() => { if (watchHost && hostToken !== capturedToken.current) deny(); }, [hostToken, watchHost, deny]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty || busyRef.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    if (!overview || context.scope || context.sessionToken || !current()) return;
    if (!rememberLocalWorkspaceSelection(projectId) || !rememberLocalStudioSelection(projectId, module, selected?.id)) setNotice('浏览器无法记住本次选择；资产已经保存在服务端，可以从项目列表重新打开。');
  }, [overview, context.scope, context.sessionToken, current, projectId, module, selected?.id]);
  const refreshedAsset = useCallback((asset: StudioAsset) => {
    selectionEpoch.current += 1;
    setSelected(asset); setRows(previous => [...previous.filter(row => row.id !== asset.id), asset]); setLineageDirty(false); setRelationshipDirty(false);
    void query.invalidateQueries({ queryKey: [cacheKey, projectId, 'assets'] });
    setStorage(undefined);
  }, [query, cacheKey, projectId]);
  const declared = useCallback((asset: StudioAsset) => client.lineage(asset.id, { expected_version: asset.version, origin: 'EXTERNAL_IMPORT', parent_asset_ids: [], chapter_ids: [], license: { label: 'UNSPECIFIED', source: '', note: '' }, operation: '外部文件导入' }), [client]);
  const adapter = useMemo<AssetLibraryAdapter>(() => ({
    cacheKey, canMutate: writable, mutationsBlocked: dirty || busy, canImport: overview?.capabilities.manual_import === true && overview.capabilities.media_validator_configured, isCurrent: current,
    list: async () => { const result = await guarded(() => client.assets()); setRows(result.items); return result.items; },
    upload: async body => {
      if (!writable || !overview?.capabilities.media_validator_configured || !['image', 'video', 'audio'].includes(body.kind)) throw new Error('请核对媒体校验工具，并选择支持的图片、音频或视频文件。');
      if (busyRef.current || dirtyRef.current) throw new Error('请先保存或放弃当前输入，再导入其他资产。');
      busyRef.current = true; setBusy(true); setNotice('');
      const identity = JSON.stringify([body.filename, body.kind, body.content_base64]);
      if (lastImport.current?.body !== identity) lastImport.current = { body: identity, key: crypto.randomUUID() };
      try {
        const imported = await guarded(() => client.importAsset({ filename: body.filename, kind: body.kind as 'image' | 'video' | 'audio', content_base64: body.content_base64, idempotency_key: lastImport.current!.key }));
        // Saving provenance is a second mutation. A failed declaration never repeats the import.
        try { const asset = await guarded(() => declared(imported)); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); return asset; }
        catch (reason) { if (!current()) throw reason; setPendingDeclaration(imported); setNotice('文件已保存，来源声明尚未保存。可仅重试声明，无需重新上传。'); return imported; }
      } finally { busyRef.current = false; if (alive.current) { setBusy(false); setStorage(undefined); } }
    },
    download: asset => overview?.capabilities.manual_export === true ? guarded(() => client.download(asset.id)) : Promise.reject(new Error('当前无法导出资产。')),
    remove: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能删除资产。')); busyRef.current = true; setBusy(true); return guarded(() => client.remove(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (alive.current) { setBusy(false); setStorage(undefined); } }); },
    trash: async () => { const value = await guarded(() => client.assets(true)); const items = value.items.filter(asset => !!asset.deleted_at); return { items, total: items.length }; },
    restore: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能恢复资产。')); busyRef.current = true; setBusy(true); return guarded(() => client.restore(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (alive.current) { setBusy(false); setStorage(undefined); } }); },
  }), [cacheKey, writable, dirty, busy, overview?.capabilities.manual_import, overview?.capabilities.manual_export, overview?.capabilities.media_validator_configured, current, guarded, client, declared]);
  useEffect(() => {
    if (!overview || !requestedAssetId) return;
    let active = true; const epoch = ++selectionEpoch.current;
    void guarded(() => client.asset(requestedAssetId)).then(asset => { if (active && epoch === selectionEpoch.current) setSelected(asset); }).catch(reason => { if (active && epoch === selectionEpoch.current && current()) setNotice(apiErrorView(reason, '上次资产当前不可读，请重新选择。').message); });
    return () => { active = false; };
  }, [overview?.project.id, requestedAssetId, guarded, client, current]);
  const loadStorage = async () => {
    if (storageReading.current || !current()) return;
    storageReading.current = true; setStorageLoading(true);
    try { setStorage(await guarded(() => client.storage())); }
    catch (reason) { if (current()) setNotice(apiErrorView(reason, '存储统计读取失败。').message); }
    finally { storageReading.current = false; if (alive.current) setStorageLoading(false); }
  };
  const refreshSelectedAsset = async (assetId: string) => {
    if (busyRef.current || !current()) return;
    const epoch = ++selectionEpoch.current;
    busyRef.current = true; setBusy(true); setReadingAsset(true);
    try { const asset = await guarded(() => client.asset(assetId)); if (epoch === selectionEpoch.current) refreshedAsset(asset); }
    catch (reason) { if (current()) setNotice(apiErrorView(reason, '资产读取失败。').message); }
    finally { busyRef.current = false; if (alive.current) { setBusy(false); setReadingAsset(false); } }
  };
  const navigate = (action: () => void) => {
    if (busyRef.current) { setNotice('当前操作尚未结束，请等待结果确认后再离开。'); return; }
    if (dirty) { setDiscard(false); setPendingNavigation(() => action); return; }
    action();
  };
  const savePreferences = async () => {
    if (!preferences || !writable || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      const saved = await guarded(() => client.savePreferences({ intents: preferences.intents, preset: preferences.preset, custom_intent: preferences.custom_intent }, preferences.version));
      setPreferences(saved); setOverview(value => value && { ...value, preferences: saved }); setNotice('创作偏好已保存。所有模块和素材保持可用。');
    } catch (reason) { if (current()) setError(apiErrorView(reason, '偏好保存失败，当前输入已保留。').message); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  };
  const sidebar = <div className="independent-studio-sidebar"><h2>独立创作</h2><p>图片、视频和声音共享项目资产。连接其它模块由你决定。</p><Button onClick={() => navigate(onProjectChoice)}>返回项目列表</Button>
    {preferences && <details><summary>创作意图与推荐布局</summary><p>可跳过、可多选。布局选项仅保存偏好，当前不会调整界面。偏好不限制模块和权限，也不会执行任务。</p><fieldset disabled={!writable || busy}><legend>这次想做什么？</legend>{intents.map(([id, label]) => <label key={id}><input type="checkbox" checked={preferences.intents.includes(id)} onChange={event => setPreferences({ ...preferences, intents: event.target.checked ? [...preferences.intents, id] : preferences.intents.filter(value => value !== id) })} />{label}</label>)}<label>自定义意图<input maxLength={240} value={preferences.custom_intent} onChange={event => setPreferences({ ...preferences, custom_intent: event.target.value })} /></label><label>布局偏好（仅保存）<select value={preferences.preset} onChange={event => setPreferences({ ...preferences, preset: event.target.value as WorkspacePreset })}>{presets.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label><Button disabled={!preferenceDirty} onClick={() => void savePreferences()}>保存创作偏好</Button></fieldset>{preferenceDirty && <p role="status">创作偏好未保存。</p>}</details>}
    <details onToggle={event => { if (event.currentTarget.open && !storage && overview) void loadStorage(); }}><summary>项目存储</summary>{storageLoading && <StatusMessage>正在核对项目存储…</StatusMessage>}{storage ? <><p>有效资产 {storage.assets.count} 项 · {storage.assets.bytes} 字节</p><p>回收站 {storage.trash.count} 项 · {storage.trash.bytes} 字节</p>
      {storage.admission?.state === 'READY' && <p>当前可导入容量估算：{storage.admission.available_import_bytes} 字节；已扣除安全预留空间和项目配额。</p>}
      {storage.admission?.state === 'LOW_SPACE_OR_QUOTA' && <StatusMessage tone="warning">空间或项目配额不足，当前无法继续导入。已有资产仍可查看和导出。</StatusMessage>}
      {storage.admission?.state === 'UNAVAILABLE' && <StatusMessage tone="warning">当前无法确认存储容量，导入将由服务端安全校验。</StatusMessage>}
      {!storage.admission && <p>容量校验状态尚未提供，上传仍由服务端核对。</p>}
      <p>以上为查询时估算；实际上传会再次校验。回收站仍占用空间，不会自动清理。</p><p>模型目录仅引用；缓存单独管理；导出位置由下载时选择。</p><p>本入口不清理或移动任何外部模型文件。</p></> : <p>展开后读取服务端统计。</p>}<Button disabled={!overview || storageLoading} onClick={() => void loadStorage()}>刷新存储统计</Button></details>
  </div>;
  const main = <div className="independent-studio">
    <Panel title="独立素材工作区"><p>无需小说、章节或模型，导入素材即可保存和导出。</p><p>上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。</p>{overview && <Badge tone="info">{!writable ? overview.capabilities.can_review === true ? '仅审核与读取' : '只读' : overview.capabilities.media_validator_configured ? '手工导入可用' : '媒体校验工具缺失'} · 不需要模型</Badge>}{overview && !overview.capabilities.media_validator_configured && <p>图片、视频和音频导入需要 FFmpeg / ffprobe 校验工具。当前可查看和导出已保存资产，未调用模型。</p>}</Panel>
    {loading && <StatusMessage>正在核对项目与权限…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {denied ? <EmptyState title="当前会话无权访问此项目" detail="私人预览已关闭。重新核对身份与范围后再打开。" /> : !overview && !loading ? <Button onClick={() => void refresh()}>重新读取项目</Button> : null}
    {pendingNavigation && <section className="creative-navigation-confirm" role="alert"><p>有未保存的偏好、来源声明或资产关联。可以继续编辑，或确认放弃后离开。</p><label><input type="checkbox" checked={discard} onChange={event => setDiscard(event.target.checked)} />确认放弃未保存输入</label><Button disabled={!discard} onClick={() => { const action = pendingNavigation; setPendingNavigation(undefined); setLineageDirty(false); setRelationshipDirty(false); setFormRevision(value => value + 1); setPreferences(overview?.preferences); action(); }}>确认离开</Button><Button onClick={() => setPendingNavigation(undefined)}>继续编辑</Button></section>}
    {pendingDeclaration && !denied && <Button disabled={!writable || busy || lineageDirty || relationshipDirty} onClick={() => { if (busyRef.current || lineageDirtyRef.current || relationshipDirtyRef.current) return; busyRef.current = true; setBusy(true); void guarded(() => declared(pendingDeclaration)).then(asset => { refreshedAsset(asset); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); }).catch(reason => { if (current()) setNotice(apiErrorView(reason, '来源声明仍未保存，文件已保留。').message); }).finally(() => { busyRef.current = false; if (alive.current) setBusy(false); }); }}>仅重试外部导入声明</Button>}
    {overview && !denied && <AssetLibraryPanel novelId={projectId} adapter={adapter} selectedAssetId={selected?.id} onSelectAsset={asset => navigate(() => { selectionEpoch.current += 1; setSelected(asset); setLineageDirty(false); setRelationshipDirty(false); })} />}
  </div>;
  const extra = selected && <>{selected.provenance && <section className="independent-studio-lineage" aria-label="独立资产来源"><p>版本 v{selected.version} · {selected.provenance.origin} · {selected.provenance.integrity}</p><p>许可：{selected.provenance.license.label}（作者声明，未作法律验证）</p>{selected.provenance.stale && <StatusMessage tone="warning">来源已变化或不可用，请核对后再复用。</StatusMessage>}
    <AssetLineageForm key={`${selected.id}:${selected.version}:${formRevision}`} row={lineageAsset(selected)} assets={rows.map(lineageAsset)} readOnly={!writable || busy || relationshipDirty} onDirtyChange={setLineageDirty} saved={() => {}} saveLineage={async body => { if (busyRef.current || !writable || relationshipDirtyRef.current) throw new Error('请先保存或放弃关联输入，再保存来源声明。'); busyRef.current = true; setBusy(true); try { const value = await guarded(() => client.lineage(selected.id, body)); refreshedAsset(value); setNotice('来源声明已保存。'); return value; } finally { busyRef.current = false; if (alive.current) setBusy(false); } }} />
    <Button disabled={busy} onClick={() => navigate(() => { void refreshSelectedAsset(selected.id); })}>重新读取当前资产</Button>
  </section>}
    <AssetRelationshipsPanel key={`${selected.id}:${selected.version}:${formRevision}`} asset={selected} client={client} canMutate={writable} canReview={overview?.capabilities.can_review === true && !denied} blocked={lineageDirty} busy={busy} isCurrent={current} read={guarded} onDirtyChange={setRelationshipDirty} mutate={async operation => {
      if (busyRef.current || lineageDirtyRef.current || !current()) throw new Error('请先保存或放弃来源输入，再修改关联。');
      busyRef.current = true; setBusy(true);
      try { const asset = await guarded(operation); refreshedAsset(asset); setNotice('关联已保存，原文件和引用内容未改变。'); return asset; }
      finally { busyRef.current = false; if (alive.current) setBusy(false); }
    }} />
  </>;
  return <AppShell module={module} onModuleChange={next => navigate(() => onModuleChange(next))} scope={{ ...scope, project: overview?.project.title || scope.project }} projectNoun={overview?.project.entry_kind === 'NEUTRAL_STUDIO' ? '项目' : undefined} actor={actor} sidebar={sidebar} main={main}
    inspector={<AssetInspector asset={denied ? undefined : selected} novelId={projectId} downloadAsset={adapter.download} isCurrent={current} showReferences={false} extra={extra} />}
    status={<>{denied ? '权限失效' : loading ? '正在核对' : busy ? readingAsset ? '读取中' : '保存中' : dirty || pendingDeclaration ? '未保存' : '已保存'} · 独立素材 · 无模型调用{status}</>} />;
}
