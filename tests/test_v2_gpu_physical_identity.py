"""GPU physical-identity regression: one physical GPU must never be counted twice.

The defect this pins: DXGI reported the single RTX 5080 on this host as **two**
hardware adapters with different AdapterLuids but identical vendor/device/subsystem/
revision. Because `_gpu_capability` deliberately fails closed when it does not see
exactly one device, that alias silently reduced the whole machine to
`gpu_vendor_id=None, vram_mib=0` — no GPU capability at all, which feeds VRAM budgets,
hardware profiles and runtime admission.

The fix does not simply de-duplicate: adapters are grouped by device signature, and a
group is collapsed **only** when the Windows present-device inventory proves exactly
one started device carries that hardware ID. Two identical physical GPUs therefore stay
two devices, an unreadable inventory collapses nothing, and every collapse is disclosed
with both counts and all AdapterLuids.
"""
from __future__ import annotations

import inspect
import sys

import pytest

from app.provider_runtime_v2_host_hardware_inventory import (
    MIB,
    HostGpuFact,
    WindowsHostHardwareProbe,
    _gpu_capability,
    present_display_hardware_ids,
    resolve_physical_gpus,
)

# Real values captured from this host's DXGI enumeration.
RTX_5080_LUID_A = "0:68850"
RTX_5080_LUID_B = "0:112158"
RTX_5080_VRAM = 16_753_098_752
RTX_5080_HARDWARE_ID = "PCI\\VEN_10DE&DEV_2C02&SUBSYS_209610DE&REV_A1"


def rtx_5080(luid: str, vram: int = RTX_5080_VRAM) -> HostGpuFact:
    return HostGpuFact(
        pci_vendor_id=0x10DE,
        dedicated_vram_bytes=vram,
        name="NVIDIA GeForce RTX 5080",
        device_id=0x2C02,
        subsystem_id=0x209610DE,
        revision=0xA1,
        adapter_luid=luid,
    )


ALIASED = (rtx_5080(RTX_5080_LUID_A), rtx_5080(RTX_5080_LUID_B))


# --- identity is preserved, not discarded ----------------------------------

def test_device_identity_matches_the_pnp_spelling():
    fact = rtx_5080(RTX_5080_LUID_A)
    assert fact.hardware_id == RTX_5080_HARDWARE_ID
    assert fact.device_signature == (0x10DE, 0x2C02, 0x209610DE, 0xA1)
    assert fact.adapter_luid == RTX_5080_LUID_A


def test_fact_keeps_full_identity_from_a_dxgi_description():
    fact = WindowsHostHardwareProbe._fact_from_dxgi_description(
        0x10DE, RTX_5080_VRAM, 0, "NVIDIA GeForce RTX 5080",
        device_id=0x2C02, subsystem_id=0x209610DE, revision=0xA1,
        adapter_luid=RTX_5080_LUID_A,
    )
    assert fact is not None
    assert fact.hardware_id == RTX_5080_HARDWARE_ID
    assert fact.adapter_luid == RTX_5080_LUID_A


def test_software_adapter_is_still_excluded():
    assert WindowsHostHardwareProbe._fact_from_dxgi_description(
        0x1414, 0, 2, "Microsoft Basic Render Driver"
    ) is None


def test_legacy_three_argument_construction_is_unchanged():
    """The identity fields must not disturb existing callers or equality."""
    assert WindowsHostHardwareProbe._fact_from_dxgi_description(
        0x10DE, 16 * MIB, 0
    ) == HostGpuFact(0x10DE, 16 * MIB)


# --- the alias is resolved, and disclosed ----------------------------------

def test_two_adapters_for_one_present_device_are_one_physical_gpu():
    devices, diagnostics = resolve_physical_gpus(ALIASED, (RTX_5080_HARDWARE_ID,))
    assert len(devices) == 1
    assert devices[0].adapter_luid == RTX_5080_LUID_A
    assert diagnostics["raw_adapter_count"] == 2
    assert diagnostics["physical_device_count"] == 1
    assert diagnostics["aliased_adapter_count"] == 1
    assert diagnostics["presence_verified"] is True
    assert diagnostics["unresolved_signatures"] == []


def test_aliasing_is_disclosed_with_every_luid_not_swallowed():
    _, diagnostics = resolve_physical_gpus(ALIASED, (RTX_5080_HARDWARE_ID,))
    assert diagnostics["adapter_luids"] == [RTX_5080_LUID_A, RTX_5080_LUID_B]
    assert diagnostics["hardware_ids"] == [RTX_5080_HARDWARE_ID, RTX_5080_HARDWARE_ID]
    assert diagnostics["present_device_counts"][RTX_5080_HARDWARE_ID] == 1


def test_two_identical_physical_gpus_stay_two_devices():
    """Requirement: a real multi-GPU machine must report multiple devices."""
    devices, diagnostics = resolve_physical_gpus(
        ALIASED, (RTX_5080_HARDWARE_ID, RTX_5080_HARDWARE_ID)
    )
    assert len(devices) == 2
    assert diagnostics["aliased_adapter_count"] == 0
    assert diagnostics["unresolved_signatures"] == []


def test_unreadable_presence_inventory_collapses_nothing():
    """No proof, no collapse: the count stays fail-closed and says why."""
    devices, diagnostics = resolve_physical_gpus(ALIASED, None)
    assert len(devices) == 2
    assert diagnostics["aliased_adapter_count"] == 0
    assert diagnostics["presence_verified"] is False
    assert diagnostics["unresolved_signatures"] == [RTX_5080_HARDWARE_ID]
    assert diagnostics["present_device_counts"][RTX_5080_HARDWARE_ID] == -1


def test_present_but_different_device_is_not_collapsed():
    other = HostGpuFact(0x10DE, 8 * MIB, "Second GPU",
                        device_id=0x2C02, subsystem_id=0x209610DE, revision=0xA2,
                        adapter_luid="0:999")
    devices, diagnostics = resolve_physical_gpus((rtx_5080(RTX_5080_LUID_A), other), ())
    assert len(devices) == 2
    assert diagnostics["aliased_adapter_count"] == 0


def test_single_adapter_is_untouched_by_resolution():
    devices, diagnostics = resolve_physical_gpus((rtx_5080(RTX_5080_LUID_A),), ())
    assert len(devices) == 1
    assert diagnostics["raw_adapter_count"] == 1
    assert diagnostics["aliased_adapter_count"] == 0


# --- the actual consequence: capability is restored, thresholds untouched ---

def test_capability_is_lost_before_resolution_and_restored_after():
    """The bug in one assertion: two aliases meant no GPU capability at all."""
    assert _gpu_capability(ALIASED) == (None, 0)          # the defect
    devices, _ = resolve_physical_gpus(ALIASED, (RTX_5080_HARDWARE_ID,))
    vendor, vram_mib = _gpu_capability(devices)           # the fix
    assert vendor is not None
    assert vram_mib == RTX_5080_VRAM // MIB


def test_genuinely_multiple_devices_still_fail_closed_for_admission():
    """Two real devices must keep the conservative no-positive-capability rule."""
    devices, _ = resolve_physical_gpus(ALIASED, (RTX_5080_HARDWARE_ID, RTX_5080_HARDWARE_ID))
    assert _gpu_capability(devices) == (None, 0)


def test_no_vendor_or_machine_specific_value_was_hardcoded():
    import app.provider_runtime_v2_host_hardware_inventory as module

    source = inspect.getsource(module)
    for forbidden in ("5080", "16303", "16753098752", "RTX"):
        assert forbidden not in source, f"resolution must not hardcode {forbidden}"


def test_presence_probe_is_passive_and_never_raises():
    result = present_display_hardware_ids()
    assert result is None or isinstance(result, tuple)
    assert not isinstance(result, set)  # a set would hide a second identical GPU


# --- real-machine acceptance -------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="real Windows native acceptance")
def test_live_probe_never_reports_one_physical_device_twice():
    facts = WindowsHostHardwareProbe().collect()
    if facts.gpus is None:
        pytest.skip("GPU enumeration unavailable on this host")
    signatures = [gpu.device_signature for gpu in facts.gpus]
    assert len(signatures) == len(set(signatures)), "one physical device reported twice"

    diagnostics = facts.gpu_enumeration
    assert diagnostics is not None
    assert diagnostics["physical_device_count"] == len(facts.gpus)
    assert diagnostics["raw_adapter_count"] >= len(facts.gpus)
    assert (diagnostics["raw_adapter_count"]
            - diagnostics["aliased_adapter_count"]) == len(facts.gpus)


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows native acceptance")
def test_live_single_gpu_host_keeps_its_capability():
    facts = WindowsHostHardwareProbe().collect()
    if facts.gpus is None or len(facts.gpus) != 1:
        pytest.skip("host does not present exactly one physical GPU")
    vendor, vram_mib = _gpu_capability(facts.gpus)
    assert vendor is not None, "one physical GPU must yield a vendor"
    assert vram_mib == (facts.gpus[0].dedicated_vram_bytes or 0) // MIB
