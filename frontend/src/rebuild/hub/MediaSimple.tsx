/* [HERMIA-FE-20261022 U6] 普通版「媒体服务」简化配置：图片 / 视频 / 声音 各一行——选服务（来自 /api/asset-providers · /api/video-providers · /api/audio/providers）、
   密钥状态（复用下方「密钥」区 /credentials/*）、单项「验证连接」（只读 + /credentials/{p}/test，不派发）。
   不含端点/模型/启用等高级参数（仍在专业「高级」里）。后端暂无「设为默认服务」接口，所以选择只用于查看，诚实标注；需求已写进给 dot 的接口文档。 */
import {useState} from 'react';
import {rb, CREDENTIAL_PROVIDERS} from '../rebuildApi';
import {runtimeCodeLabel} from '../../ui/runtimeCodeLabels';

export type MediaKind = 'image' | 'video' | 'audio';
export type MediaItem = {id: string; name: string; local: boolean; needsKey: boolean; keyFilled: boolean; usable: boolean; reachable: boolean | null};
const KIND_LABEL: Record<MediaKind, string> = {image: '图片', video: '视频', audio: '声音'};

export function mediaItemsFrom(kind: MediaKind, items: any[] | null | undefined): MediaItem[] {
  return (items || []).map((p: any) => ({
    id: String(kind === 'video' ? p.id ?? p.provider_id : p.provider_id ?? p.id),
    name: p.display_name || `${KIND_LABEL[kind]}服务`,
    local: !!p.local,
    needsKey: !p.local && p.requires_credential !== false,
    keyFilled: !!p.credential_configured,
    usable: kind === 'video' ? !!(p.registered || p.available) : !!p.configured,
    reachable: p.reachable === true ? true : p.reachable === false ? false : null,
  }));
}

function keyText(m: MediaItem) {
  if (m.local) return '本地服务，不需要密钥';
  if (!m.needsKey) return '不需要密钥';
  return m.keyFilled ? '密钥已填' : '还没填密钥';
}

export function MediaSimple({data, onReload}: {data: Partial<Record<MediaKind, any[] | null>> | null; onReload: () => Promise<void>}) {
  const [pick, setPick] = useState<Record<MediaKind, number>>({image: 0, video: 0, audio: 0});
  const [busy, setBusy] = useState<MediaKind | null>(null);
  const [result, setResult] = useState<Partial<Record<MediaKind, {ok: boolean | null; text: string}>>>({});
  async function check(kind: MediaKind, m: MediaItem) {
    setBusy(kind);
    try {
      if (m.needsKey && m.keyFilled && (CREDENTIAL_PROVIDERS as readonly string[]).includes(m.id)) {
        const r = await rb.testCredential(m.id).catch((e: any) => ({reachable: false, err: e}));
        setResult(s => ({...s, [kind]: r.reachable ? {ok: true, text: '能连上'} : {ok: false, text: `连不上${(r as any).err?.code ? `（${runtimeCodeLabel((r as any).err.code)}）` : ''}`}}));
      } else if (m.needsKey && !m.keyFilled) {
        setResult(s => ({...s, [kind]: {ok: null, text: '先在下方「密钥」里填好，再来验证。'}}));
      } else {
        await onReload();
        setResult(s => ({...s, [kind]: {ok: null, text: m.reachable === true ? '已重新读取状态：能连上' : '已重新读取状态，这个服务暂时没法单独测试连接。'}}));
      }
    } finally { setBusy(null); }
  }
  return (
    <section className="hub-sec" aria-label="媒体服务" data-hub-media="simple"><h4>媒体服务</h4>
      <p className="hub-muted">给图片、视频、声音各看一个服务的状态。现在默认按「本地优先」自动选，这里的选择只用来查看，暂时不能保存为默认。</p>
      {data === null ? <p className="hub-muted">读取中…</p> : (['image', 'video', 'audio'] as const).map(kind => {
        const list = mediaItemsFrom(kind, data[kind]);
        const m = list[Math.min(pick[kind], Math.max(list.length - 1, 0))];
        const r = result[kind];
        return <div key={kind} className="model-row hub-media-row" data-media-kind={kind}>
          <b>{KIND_LABEL[kind]}</b>
          {list.length === 0 ? <span className="hub-muted">还没有可用的{KIND_LABEL[kind]}服务</span> : <>
            <select aria-label={`${KIND_LABEL[kind]}服务`} value={pick[kind]} onChange={e => { setPick(p => ({...p, [kind]: Number(e.target.value)})); setResult(s => ({...s, [kind]: undefined})); }}>
              {list.map((x, i) => <option key={i} value={i}>{x.name}</option>)}
            </select>
            <span className={`hub-badge hub-badge--${m.local ? 'local' : m.keyFilled ? 'part' : 'off'}`}>{keyText(m)}</span>
            {m.needsKey && !m.keyFilled ? <a className="nv-btn" href="#hub-keys">去填密钥</a> : null}
            <button type="button" className="nv-btn" disabled={busy === kind} onClick={() => void check(kind, m)}>{busy === kind ? '验证中…' : '验证连接'}</button>
            {r ? <span role="status" className={`hub-badge hub-badge--${r.ok === true ? 'ok' : 'off'}`}>{r.text}</span> : null}
          </>}
        </div>;
      })}
    </section>
  );
}
