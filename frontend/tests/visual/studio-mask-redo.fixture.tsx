/** Browser-only synthetic fixture. Uses the real draft, canvas and shared shell; no API client. */
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AppShell } from '../../src/ui/AppShell';
import { Panel } from '../../src/ui/primitives';
import { StudioBinaryMaskCanvas } from '../../src/creative/StudioBinaryMaskCanvas';
import { BinaryMaskDraft } from '../../src/creative/studioBinaryMask';
import '../../src/creative/creative.css';
import '../../src/experimental/experimental.css';

export async function mount() {
  const source = document.createElement('canvas'); source.width = 64; source.height = 64;
  const context = source.getContext('2d')!, pixels = context.createImageData(64, 64);
  for (let i = 0; i < pixels.data.length; i += 4) {
    pixels.data[i] = 80; pixels.data[i + 1] = 140; pixels.data[i + 2] = 200; pixels.data[i + 3] = 255;
  }
  context.putImageData(pixels, 0, 0);
  const blob = await new Promise<Blob>(resolve => source.toBlob(value => resolve(value!)));
  const sourceUrl = URL.createObjectURL(blob), mask = new BinaryMaskDraft(64, 64);
  function Fixture() {
    const [changes, setChanges] = useState(0);
    return <AppShell module="IMAGE" onModuleChange={() => {}} actor="本地检查"
      scope={{ workspace: '创作工作区', project: '蒙版重做检查', storyline: '主线', branch: '本地草稿' }}
      sidebar={<p>合成来源 · 64 × 64 PNG</p>}
      main={<Panel title="手工二值遮罩"><StudioBinaryMaskCanvas mask={mask} sourceUrl={sourceUrl} readOnly={false} isCurrent={() => true} onChange={() => setChanges(value => value + 1)} /></Panel>}
      inspector={<p>局部编辑通知：{changes}。此检查不连接后端或执行生成。</p>} status="本地合成数据检查" />;
  }
  const host = document.createElement('div'); document.body.replaceChildren(host);
  createRoot(host).render(<Fixture />);
}
