import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Download, Trash2, Upload } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiErrorView, type Asset } from "../api";
import { Button, EmptyState, IconButton, Panel } from "../ui/primitives";
import { useRequestedRecord } from "../experimental/useRequestedRecord";
import { useStudio } from "../store";

export const MAX_ASSET_BYTES = 25 * 1024 * 1024;
/** Explicit owner adapter. Omitted consumers retain the original asset API. */
export type AssetLibraryAdapter = {
  cacheKey: string;
  canMutate: boolean;
  canImport?: boolean;
  mutationsBlocked?: boolean;
  isCurrent: () => boolean;
  list: () => Promise<Asset[]>;
  upload: (body: { filename: string; content_base64: string; media_type?: string; kind: string }) => Promise<Asset>;
  download: (asset: Asset) => Promise<Blob>;
  remove: (asset: Asset) => Promise<unknown>;
  trash: () => Promise<{ items: Asset[]; total: number }>;
  restore: (asset: Asset) => Promise<unknown>;
};
let requestedAssetSequence = 0;
// A local, non-network placeholder keeps the accessible image node present
// while the authenticated DesktopHost download is in flight.
const IMAGE_PLACEHOLDER_DATA_URI =
  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"%3E%3Crect width="2" height="2" fill="%23e7ebf0"/%3E%3C/svg%3E';

export function AssetLibraryPanel({
  novelId,
  characterId,
  sceneId,
  selectedAssetId,
  requestedAssetId,
  onSelectAsset,
  adapter,
}: {
  novelId: string;
  characterId?: string;
  sceneId?: string;
  selectedAssetId?: string;
  requestedAssetId?: string;
  onSelectAsset?: (asset?: Asset) => void;
  adapter?: AssetLibraryAdapter;
}) {
  const authority = useStudio(state => JSON.stringify([state.sessionToken, state.actor?.id, state.actor?.workspaceId,
    state.scope?.workspaceId, state.scope?.projectId, state.scope?.storylineId, state.scope?.branchId]));
  // A targeted source read must not reuse an older session/branch's in-flight
  // list. Only this opaque observer enters React Query; credentials stay local.
  const observer = useMemo(() => ++requestedAssetSequence, [authority, novelId, requestedAssetId]);
  const client = useQueryClient(),
    input = useRef<HTMLInputElement>(null),
    uploadPending = useRef(false),
    [error, setError] = useState<unknown>(),
    [uploading, setUploading] = useState(false),
    [kind, setKind] = useState(""),
    [showTrash, setShowTrash] = useState(false),
    [search, setSearch] = useState("");
  const assetPrefix = adapter ? [adapter.cacheKey, novelId, 'assets'] : ['assets', novelId];
  const trashPrefix = adapter ? [adapter.cacheKey, novelId, 'trash'] : ['asset-trash', novelId];
  const canMutate = !adapter || adapter.canMutate;
  const canImport = canMutate && adapter?.canImport !== false && !adapter?.mutationsBlocked;
  const assets = useQuery({
    queryKey: [...assetPrefix, kind, characterId, sceneId, ...(requestedAssetId ? [observer] : [])],
    queryFn: () => adapter ? adapter.list().then(rows => rows.filter(row => !kind || row.kind === kind)) : api.assets(novelId, kind || undefined, characterId, sceneId),
    enabled: !!novelId,
    refetchOnMount: requestedAssetId ? 'always' : true,
  });
  useEffect(() => { setKind(''); setShowTrash(false); }, [requestedAssetId]);
  const requestedReady = assets.isFetchedAfterMount && !assets.isFetching && !assets.error;
  const requested = useRequestedRecord(requestedAssetId, assets.data, !!requestedReady, observer);
  const remove = useMutation({
    mutationFn: (asset: Asset) => adapter ? adapter.remove(asset) : api.deleteAsset(asset.id, novelId),
    onSuccess: async (_, asset) => {
      if (adapter && !adapter.isCurrent()) return;
      if (selectedAssetId === asset.id) onSelectAsset?.();
      await client.invalidateQueries({ queryKey: assetPrefix });
      await client.invalidateQueries({ queryKey: trashPrefix });
    },
  });
  const trash = useQuery({
    queryKey: trashPrefix,
    queryFn: () => adapter ? adapter.trash() : api.assetTrash(novelId),
    enabled: !!novelId && showTrash,
  });
  const restore = useMutation({
    mutationFn: (asset: Asset) => adapter ? adapter.restore(asset) : api.restoreAsset(novelId, asset.id),
    onSuccess: async () => {
      if (adapter && !adapter.isCurrent()) return;
      await client.invalidateQueries({ queryKey: assetPrefix });
      await client.invalidateQueries({ queryKey: trashPrefix });
    },
  });
  async function upload(file?: File) {
    if (!file || !novelId || uploading || uploadPending.current || !canImport) return;
    const originAdapter = adapter;
    const current = () => !originAdapter || originAdapter.isCurrent();
    setError(undefined);
    if (file.size === 0) {
      setError(new Error("不能上传空文件。"));
      return;
    }
    if (file.size > MAX_ASSET_BYTES) {
      setError(new Error("资产不能超过 25 MiB。"));
      return;
    }
    uploadPending.current = true;
    setUploading(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (!current()) return;
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 0x8000)
        binary += String.fromCharCode(
          ...bytes.subarray(offset, offset + 0x8000),
        );
      const body = {
        filename: file.name,
        media_type: file.type || undefined,
        kind: file.type.startsWith("image/") || originAdapter && !file.type && /\.(png|jpe?g|webp)$/i.test(file.name) ? "image" : originAdapter && file.type.startsWith('video/') ? 'video' : originAdapter && file.type.startsWith('audio/') ? 'audio' : "file",
        content_base64: btoa(binary),
      };
      const saved = originAdapter ? await originAdapter.upload(body) : await api.uploadAsset(novelId, body);
      if (!current()) return;
      await client.invalidateQueries({ queryKey: assetPrefix });
      if (originAdapter) onSelectAsset?.(saved);
    } catch (reason) {
      if (current()) setError(reason);
    } finally {
      uploadPending.current = false;
      if (current()) setUploading(false);
    }
  }
  return (
    <Panel
      title="资产库"
      className="asset-library"
      actions={
        <Button
          type="button"
          variant="primary"
          disabled={uploading || !novelId || !canImport}
          onClick={() => input.current?.click()}
        >
          <Upload aria-hidden="true" />
          {uploading ? "上传中…" : "上传资产"}
        </Button>
      }
    >
      <input
        ref={input}
        hidden
        type="file"
        accept={adapter ? 'image/png,image/jpeg,image/webp,audio/*,video/*' : "image/*,audio/*,video/*,.txt,.md,.markdown,.json,.docx,.pdf"}
        aria-label="选择要上传的资产文件"
        disabled={uploading || !novelId || !canImport}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          void upload(file);
        }}
      />
      {Boolean(error) && (
        <AssetError error={error} fallback="资产上传失败，请重试。" />
      )}
      {Boolean(assets.error) && (
        <AssetError error={assets.error} fallback="资产加载失败，请重试。" />
      )}
      {Boolean(remove.error) && (
        <AssetError error={remove.error} fallback="资产删除失败，请重试。" />
      )}
      {!novelId && (
        <p role="status" className="novel-help">
          请先打开一个小说项目，再管理项目资产。
        </p>
      )}
      {uploading && (
        <p role="status" className="novel-help" aria-live="polite">
          正在安全写入资产…
        </p>
      )}
      {adapter && !canMutate && <p role="status">资产文件当前只读，可以查看和导出已有资产。</p>}
      {assets.isLoading && (
        <p role="status" aria-live="polite">
          正在加载资产…
        </p>
      )}
      {Boolean(assets.error) && !assets.isFetching && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => void assets.refetch()}
        >
          重新加载资产
        </Button>
      )}
      {novelId &&
        !assets.isLoading &&
        !assets.error &&
        !assets.data?.length && (
          <EmptyState title="暂无资产" detail="上传图片或其他创作素材。" />
        )}
      <div className="asset-library__toolbar">
        {adapter && <label>查找资产<input type="search" aria-label="查找资产" value={search} maxLength={200} onChange={event => setSearch(event.target.value)} /></label>}
        <label>
          类型筛选
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">全部</option>
            <option value="image">图片</option>
            <option value="video">视频</option>
            <option value="audio">音频</option>
          </select>
        </label>
        <small>{assets.data?.length || 0} 项资产</small>
        <Button type="button" variant="ghost" disabled={!novelId} aria-pressed={showTrash}
          onClick={() => setShowTrash(!showTrash)}>回收站</Button>
      </div>
      <p className="novel-help">删除后原素材进入回收站，可恢复。已绑定的参考需重新审核后才能参与检索。</p>
      {showTrash && <section aria-label="资产回收站">
        <p className="novel-help">恢复前会校验原文件的大小和 SHA-256，损坏文件不会被恢复。</p>
        {trash.isLoading && <p role="status">正在读取回收站…</p>}
        {Boolean(trash.error) && <AssetError error={trash.error} fallback="回收站读取失败。"/>}
        {Boolean(trash.error) && <Button variant="ghost" onClick={() => void trash.refetch()}>重试回收站</Button>}
        {Boolean(restore.error) && <AssetError error={restore.error} fallback="资产恢复失败。"/>}
        {!trash.isLoading && !trash.error && trash.data?.total === 0 && <p role="status">回收站为空。</p>}
        {trash.data?.items.map(asset => <article key={asset.id}>
          <span>{asset.filename}</span>
          <Button variant="ghost" disabled={restore.isPending || !canMutate || adapter?.mutationsBlocked} onClick={() => restore.mutate(asset)}>
            {restore.isPending && restore.variables?.id === asset.id ? "恢复中…" : "恢复资产"}
          </Button>
        </article>)}
      </section>}
      <div className="novel-record-list asset-library__grid">
        {adapter && search.trim() && assets.data?.length && !assets.data.some(asset => asset.filename.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) ? <p role="status">没有匹配资产。</p> : null}
        {requested.missing && <p role="status">请求的原资产当前不可读或已移除，请刷新搜索。</p>}
        {(!requestedAssetId || requestedReady) && assets.data?.filter(asset => !search.trim() || asset.filename.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).map((asset) => (
          <AssetCard
            key={asset.id}
            asset={asset}
            selected={(selectedAssetId || requestedAssetId) === asset.id}
            focusRef={requestedAssetId === asset.id ? requested.ref : undefined}
            onSelect={() => onSelectAsset?.(asset)}
            onDelete={() => {
              remove.mutate(asset);
            }}
            deleting={remove.isPending && remove.variables?.id === asset.id}
            adapter={adapter}
          />
        ))}
      </div>
    </Panel>
  );
}

/**
 * Downloads go through the API client instead of a bare anchor/image URL so
 * the DesktopHost session header is preserved in packaged and collaboration
 * mode. Object URLs are kept in memory only and revoked when the card leaves
 * the tree.
 */
function AssetCard({
  asset,
  onDelete,
  onSelect,
  selected,
  deleting,
  focusRef,
  adapter,
}: {
  asset: Asset;
  onDelete: () => void;
  onSelect: () => void;
  selected: boolean;
  deleting: boolean;
  focusRef?: RefObject<HTMLElement>;
  adapter?: AssetLibraryAdapter;
}) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewLoading, setPreviewLoading] = useState(
    asset.media_type.startsWith("image/"),
  );
  const [downloadError, setDownloadError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    if (!asset.media_type.startsWith("image/")) {
      setPreviewLoading(false);
      return () => {
        active = false;
      };
    }
    setPreviewLoading(true);
    setPreviewUrl("");
    void (adapter ? adapter.download(asset) : api.assetDownload(asset.id,asset.novel_id))
      .then((blob) => {
        if (!active || adapter && !adapter.isCurrent()) return;
        try {
          setPreviewUrl(URL.createObjectURL(blob));
        } catch {
          setPreviewUrl("");
        }
      })
      .catch(() => {
        if (active) setPreviewUrl("");
      })
      .finally(() => {
        if (active) setPreviewLoading(false);
      });
    return () => {
      active = false;
    };
  }, [asset.id, asset.media_type, asset.novel_id, asset.sha256, adapter]);
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );
  async function download() {
    setDownloadError(undefined);
    try {
      const blob = await (adapter ? adapter.download(asset) : api.assetDownload(asset.id,asset.novel_id));
      if (adapter && !adapter.isCurrent()) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download =
        asset.filename.replace(/[\\/\r\n\0]/g, "_").slice(0, 255) || "asset";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (reason) {
      setDownloadError(reason);
    }
  }
  return (
    <article className={selected ? "is-selected" : ""} aria-label={`资产 ${asset.filename}`} aria-current={focusRef ? 'true' : undefined} tabIndex={focusRef ? -1 : undefined} ref={focusRef}>
      <button
        type="button"
        className="asset-card__select"
        aria-pressed={selected}
        aria-label={`检查资产 ${asset.filename}`}
        onClick={onSelect}
      >
      {asset.media_type.startsWith("image/") && (
        <div
          className="asset-preview"
          aria-label={`${asset.filename} 图片预览`}
          aria-busy={previewLoading}
        >
          <img
            src={previewUrl || IMAGE_PLACEHOLDER_DATA_URI}
            alt={asset.filename}
            loading="lazy"
            onError={() => setPreviewUrl("")}
            style={{
              maxWidth: "240px",
              maxHeight: "160px",
              objectFit: "contain",
            }}
          />
          {!previewUrl && (
            <span className="novel-help">
              {previewLoading ? "正在读取预览…" : "暂无可用预览"}
            </span>
          )}
        </div>
      )}
      <header>
        <strong>{asset.filename}</strong>
        <span>{Math.ceil(asset.size / 1024)} KB</span>
      </header>
      <p>
        {asset.media_type} · {asset.sha256.slice(0, 12)}
      </p>
      {adapter && <p>已保存 · v{asset.version} · {asset.provenance?.origin === 'EXTERNAL_IMPORT' ? '外部导入' : '来源待声明'}</p>}
      </button>
      {Boolean(downloadError) && (
        <AssetError error={downloadError} fallback="下载失败，请重试。" />
      )}
      <footer>
        <Button
          type="button"
          variant="ghost"
          disabled={deleting}
          onClick={() => void download()}
        >
          <Download aria-hidden="true" />
          下载
        </Button>
        <IconButton label="删除资产" disabled={deleting || !!adapter && (!adapter.canMutate || adapter.mutationsBlocked)} onClick={onDelete}>
          <Trash2 aria-hidden="true" />
        </IconButton>
      </footer>
    </article>
  );
}

function AssetError({ error, fallback }: { error: unknown; fallback: string }) {
  const view = apiErrorView(error, fallback);
  return (
    <div className="asset-error" role="alert">
      <p className="novel-error">{view.message}</p>
      <p className="asset-error__meta">
        {view.code && (
          <span>
            代码：<code>{view.code}</code>
          </span>
        )}
        {view.requestId && (
          <span>
            请求 ID：<code>{view.requestId}</code>
          </span>
        )}
        {view.details && (
          <span>
            详情：<code>{view.details}</code>
          </span>
        )}
      </p>
    </div>
  );
}
