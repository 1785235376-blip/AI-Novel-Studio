import { useEffect, useState } from "react";
import { Download, File, Image, Music2, Video } from "lucide-react";
import { api, type Asset } from "../api";
import { Button, EmptyState, StatusMessage } from "../ui/primitives";
import "./AssetInspector.css";

const formatBytes = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
};

const assetIcon = (mediaType: string) =>
  mediaType.startsWith("image/") ? <Image aria-hidden="true" /> :
  mediaType.startsWith("video/") ? <Video aria-hidden="true" /> :
  mediaType.startsWith("audio/") ? <Music2 aria-hidden="true" /> : <File aria-hidden="true" />;

export function AssetInspector({ asset, novelId }: { asset?: Asset; novelId?: string }) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const previewable = asset && /^(image|audio|video)\//.test(asset.media_type);
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setPreviewUrl(""); setError("");
    if (!asset || !previewable) return () => { active = false; };
    setLoading(true);
    api.assetDownload(asset.id).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob); setPreviewUrl(objectUrl);
    }).catch(() => { if (active) setError("媒体预览读取失败，可尝试下载原始文件。"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [asset?.id, previewable]);
  async function download() {
    if (!asset) return;
    setError("");
    try {
      const blob = await api.assetDownload(asset.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = asset.filename.replace(/[\\/\r\n\0]/g, "_").slice(0, 255) || "asset";
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch { setError("资产下载失败，请检查本地服务后重试。"); }
  }
  if (!asset) return <section className="asset-inspector" aria-label="资产检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="未选择资产" detail={novelId ? "从资产网格选择一个项目以查看真实预览和元数据。" : "请先打开小说项目。"}/></section>;
  return <section className="asset-inspector" aria-label="资产检查面板">
    <div className="workspace-inspector__eyebrow">Asset Inspector</div>
    <header>{assetIcon(asset.media_type)}<div><strong title={asset.filename}>{asset.filename}</strong><span>{asset.kind} · {asset.media_type}</span></div></header>
    <div className="asset-inspector__preview" aria-busy={loading}>
      {loading && <span>正在读取预览…</span>}
      {!loading && previewUrl && asset.media_type.startsWith("image/") && <img src={previewUrl} alt={asset.filename}/>} 
      {!loading && previewUrl && asset.media_type.startsWith("video/") && <video src={previewUrl} controls aria-label={`${asset.filename} 视频预览`}/>} 
      {!loading && previewUrl && asset.media_type.startsWith("audio/") && <audio src={previewUrl} controls aria-label={`${asset.filename} 音频预览`}/>} 
      {!loading && !previewable && <span>此文件类型没有内置预览。</span>}
    </div>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    <dl className="asset-inspector__facts"><div><dt>文件大小</dt><dd>{formatBytes(asset.size)}</dd></div><div><dt>资产 ID</dt><dd title={asset.id}>{asset.id}</dd></div><div><dt>SHA-256</dt><dd title={asset.sha256}>{asset.sha256}</dd></div><div><dt>更新时间</dt><dd>{asset.updated_at ? new Date(asset.updated_at).toLocaleString() : "未记录"}</dd></div></dl>
    <Button variant="ghost" onClick={download}><Download aria-hidden="true" size={15}/>下载原始文件</Button>
    <p className="novel-help">约束绑定和使用位置将在后续接入；当前不推断未记录的引用关系。</p>
  </section>;
}
