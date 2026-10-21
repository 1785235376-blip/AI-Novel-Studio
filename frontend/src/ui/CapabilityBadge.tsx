/**
 * [HERMIA-FE-20261022 H-P1-02] Small capability badge — undetermined never green.
 */
import {Badge} from './primitives';
import {
  capabilityBadgeView,
  type CapabilityBadgeView,
} from '../workbench/capabilityBadge';
import type {CapabilityStatus} from '../workbench/panels';

export function CapabilityBadge({
  status = 'undetermined',
  className,
  'aria-label': ariaLabel,
}: {
  status?: CapabilityStatus;
  className?: string;
  'aria-label'?: string;
}) {
  const view: CapabilityBadgeView = capabilityBadgeView(status);
  return (
    <span
      className={className}
      aria-label={ariaLabel || `能力：${view.label}`}
      data-capability={view.status}
      data-capability-tone={view.tone}
    >
      <Badge tone={view.tone}>{view.label}</Badge>
    </span>
  );
}
