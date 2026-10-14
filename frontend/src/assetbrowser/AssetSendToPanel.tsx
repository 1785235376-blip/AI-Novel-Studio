import { useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import {
  ASSET_BROWSER_NOTICES, ASSET_BROWSER_REFERENCE_IS_NOT_A_COPY, ASSET_BROWSER_SEND_TARGETS,
  ASSET_BROWSER_SEND_TARGET_HINTS, ASSET_BROWSER_SEND_TARGET_LABELS, ASSET_BROWSER_UNVERIFIED,
  type AssetBrowserReference, type AssetBrowserRow, type AssetBrowserSendTarget,
} from './assetBrowserTypes';
import { checkSendTo, sendTargetAccepts } from './assetBrowserOps';

/**
 * 「传给其他模块」面板。
 *
 * 它**只**做一件事：把原资产的 `{ asset_id, version, digest }` 通过回调交给组合根。
 * 它不会执行目标模块、不会复制内容、不会写入第二个原资产；目标模块自己决定是否
 * 使用这个引用，并且必须由用户在该模块里再确认一次。
 *
 * 拒绝路径同样重要：没有可核实的版本、或目标模块不接受这种媒体种类时，按钮不可
 * 点击，并给出原因（而不是发一个假引用出去）。
 */
export function AssetSendToPanel({
  row, busy, onSendTo,
}: {
  row: AssetBrowserRow;
  busy: boolean;
  onSendTo?: (target: AssetBrowserSendTarget, reference: AssetBrowserReference) => void;
}) {
  const [target, setTarget] = useState<AssetBrowserSendTarget | null>(null);
  const [sent, setSent] = useState<{ target: AssetBrowserSendTarget; reference: AssetBrowserReference } | null>(null);
  const check = target ? checkSendTo(row, target) : undefined;

  function emit() {
    if (!target || !onSendTo || !check?.allowed) return;
    // 只发引用：内容没有被复制，目标模块也没有被执行。
    onSendTo(target, check.reference);
    setSent({ target, reference: check.reference });
  }

  return <section className="asset-browser__send-to" aria-label="传给其他模块">
    <h4>传给其他模块</h4>
    <p className="asset-browser__note">{ASSET_BROWSER_NOTICES.notACopy}</p>
    <div className="asset-browser__actions" role="group" aria-label="选择目标模块">
      {ASSET_BROWSER_SEND_TARGETS.map(candidate => {
        const verdict = checkSendTo(row, candidate);
        return <Button key={candidate} type="button" variant="ghost" aria-pressed={target === candidate}
          disabled={busy || !onSendTo || !verdict.allowed}
          title={verdict.allowed ? ASSET_BROWSER_SEND_TARGET_HINTS[candidate] : verdict.message}
          onClick={() => { setTarget(candidate); setSent(null); }}>
          {ASSET_BROWSER_SEND_TARGET_LABELS[candidate]}
        </Button>;
      })}
    </div>
    <dl className="asset-browser__facts">
      <div><dt>资产 ID</dt><dd><code>{row.id}</code></dd></div>
      <div><dt>版本</dt><dd>{row.version === null ? ASSET_BROWSER_UNVERIFIED : `v${row.version}`}</dd></div>
      <div><dt>SHA-256</dt><dd><code>{row.digest}</code></dd></div>
    </dl>
    {target && check && !check.allowed && <StatusMessage tone="warning">{check.message}</StatusMessage>}
    {target && check?.allowed && <p className="asset-browser__note">
      目标：{ASSET_BROWSER_SEND_TARGET_LABELS[target]}（只接受 {sendTargetAccepts(target)}）。
      传参只携带上面三项；目标模块需要由你在那里再次确认。
    </p>}
    <div className="asset-browser__actions">
      <Button type="button" variant="primary" disabled={busy || !onSendTo || !check?.allowed} onClick={emit}>
        生成引用（不执行目标模块）
      </Button>
      {sent && <Badge tone="success">已发出引用 · {ASSET_BROWSER_SEND_TARGET_LABELS[sent.target]}</Badge>}
    </div>
    {sent && <p className="asset-browser__note" role="status">
      已把 {sent.reference.asset_id} · v{sent.reference.version} · {sent.reference.digest}
      的引用交给组合根。没有复制内容、没有创建第二个原资产、没有执行任何目标模块。
      （{ASSET_BROWSER_REFERENCE_IS_NOT_A_COPY}）
    </p>}
    {!onSendTo && <p className="asset-browser__note">
      组合根未提供 `onSendTo`，因此这里只能查看引用，不能发出。
    </p>}
  </section>;
}
