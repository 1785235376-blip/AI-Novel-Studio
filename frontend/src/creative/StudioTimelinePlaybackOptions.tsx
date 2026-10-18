import { useEffect, useRef, useState, type RefObject } from 'react';
import { StatusMessage } from '../ui/primitives';

/** Session-only review controls; these never change timeline speed or export jobs. */
export function StudioTimelinePlaybackOptions({ media, url, identity }: {
  media: RefObject<HTMLVideoElement>; url: string; identity: string;
}) {
  const [rate, setRate] = useState(1), [loop, setLoop] = useState(false), [error, setError] = useState('');
  const alive = useRef(true);
  const owner = useRef({ url, identity });
  if (owner.current.url !== url || owner.current.identity !== identity) owner.current = {url, identity};
  const captured = owner.current;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const currentMedia = () => {
    const element = media.current;
    return alive.current && owner.current === captured && element?.getAttribute('src') === url ? element : null;
  };
  useEffect(() => {
    setRate(1); setLoop(false); setError('');
    const element = media.current;
    if (!element || element.getAttribute('src') !== url) return;
    element.loop = false; element.playbackRate = 1;
    const observeRate = () => { if (alive.current && owner.current === captured
      && element.getAttribute('src') === url && Number.isFinite(element.playbackRate)) setRate(element.playbackRate); };
    element.addEventListener('ratechange', observeRate);
    return () => { element.removeEventListener('ratechange', observeRate); };
  }, [url, identity, media]);
  return <section aria-label="本会话播放选项">
    <label>预览播放速度<select value={rate} onChange={event => {
      const value = Number(event.currentTarget.value), element = currentMedia();
      if (!element || ![0.5, 0.75, 1, 1.25, 1.5, 2].includes(value)) return;
      try { element.playbackRate = value; setRate(value); setError(''); }
      catch { setError('浏览器未能应用此预览速度；时间线和导出设置没有改变。'); }
    }}><option value={0.5}>0.5×</option><option value={0.75}>0.75×</option><option value={1}>1×</option>
      {![0.5, 0.75, 1, 1.25, 1.5, 2].includes(rate) && <option value={rate}>当前 {rate}×</option>}
      <option value={1.25}>1.25×</option><option value={1.5}>1.5×</option><option value={2}>2×</option></select></label>
    <label><input type="checkbox" checked={loop} onChange={event => {
      const element = currentMedia(); if (!element) return;
      element.loop = event.currentTarget.checked; setLoop(element.loop);
    }} />循环播放当前已载入缓存</label>
    <p>仅影响本次浏览器预览；请手动开始播放。切换缓存后恢复 1× 并关闭循环，不改变剪辑变速、导出或审核状态，也不重新生成缓存。</p>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
