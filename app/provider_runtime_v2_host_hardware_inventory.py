"""Host-owned capability facts for the current Provider Runtime execution node."""
from __future__ import annotations

import ctypes
import platform
import re
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .model_center.domain import RuntimeManagement, RuntimeState, RuntimeType
from .model_center.runtime_profiles import managed_executable_file
from .provider_runtime_v2_contracts import ExecutionNodeIdentity, HardwareSnapshot
from .stable_identity import (
    ARCHITECTURE_ARM64,
    ARCHITECTURE_X86_64,
    GPU_VENDOR_AMD,
    GPU_VENDOR_INTEL,
    GPU_VENDOR_NVIDIA,
    RUNTIME_FAMILY_COMFYUI,
    RUNTIME_FAMILY_LLAMA_CPP,
    validate_uuid,
)


MIB = 1024 * 1024


class HostHardwareInventoryError(RuntimeError):
    """Deterministic failure raised before an invalid snapshot can be produced."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HostGpuFact:
    """One positively enumerated physical display adapter."""

    pci_vendor_id: int
    dedicated_vram_bytes: int | None


@dataclass(frozen=True)
class HostHardwareFacts:
    """Raw local facts. ``gpus=None`` means enumeration was unavailable."""

    architecture: str
    physical_ram_bytes: int
    gpus: tuple[HostGpuFact, ...] | None


_ARCHITECTURE_ALIASES = {
    "amd64": ARCHITECTURE_X86_64.taxonomy_id,
    "x86_64": ARCHITECTURE_X86_64.taxonomy_id,
    "arm64": ARCHITECTURE_ARM64.taxonomy_id,
    "aarch64": ARCHITECTURE_ARM64.taxonomy_id,
}
_GPU_VENDOR_IDS = {
    0x10DE: GPU_VENDOR_NVIDIA.taxonomy_id,
    0x1002: GPU_VENDOR_AMD.taxonomy_id,
    0x8086: GPU_VENDOR_INTEL.taxonomy_id,
}
_RUNTIME_FAMILY_IDS = {
    RuntimeType.LLAMA_CPP: RUNTIME_FAMILY_LLAMA_CPP.taxonomy_id,
    RuntimeType.COMFYUI: RUNTIME_FAMILY_COMFYUI.taxonomy_id,
}


def normalize_architecture(raw: str) -> UUID:
    if not isinstance(raw, str) or not raw.strip():
        raise HostHardwareInventoryError("UNKNOWN_ARCHITECTURE")
    architecture = _ARCHITECTURE_ALIASES.get(raw.strip().casefold())
    if architecture is None:
        raise HostHardwareInventoryError("UNKNOWN_ARCHITECTURE")
    return architecture


def _positive_physical_ram_mib(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise HostHardwareInventoryError("INVALID_HARDWARE_FACT")
    return value // MIB


def _gpu_capability(gpus: tuple[HostGpuFact, ...] | None) -> tuple[UUID | None, int]:
    # Unknown, absent and multi-device facts all fail closed to no positive GPU
    # capability. They remain distinguishable in HostHardwareFacts for diagnostics.
    if gpus is None:
        return None, 0
    if not isinstance(gpus, tuple):
        raise HostHardwareInventoryError("INVALID_HARDWARE_FACT")
    for gpu in gpus:
        if not isinstance(gpu, HostGpuFact) or type(gpu.pci_vendor_id) is not int:
            raise HostHardwareInventoryError("INVALID_HARDWARE_FACT")
        if gpu.dedicated_vram_bytes is not None and (
            type(gpu.dedicated_vram_bytes) is not int or gpu.dedicated_vram_bytes < 0
        ):
            raise HostHardwareInventoryError("INVALID_HARDWARE_FACT")
    if len(gpus) != 1:
        return None, 0
    gpu = gpus[0]
    vendor = _GPU_VENDOR_IDS.get(gpu.pci_vendor_id)
    if vendor is None:
        return None, 0
    value = gpu.dedicated_vram_bytes
    if value is None:
        return vendor, 0
    return vendor, value // MIB


def _existing_node_id(execution_node_identity: Any) -> UUID:
    store = getattr(execution_node_identity, "store", execution_node_identity)
    getter = getattr(store, "get", None)
    if not callable(getter):
        raise HostHardwareInventoryError("EXECUTION_NODE_ID_UNAVAILABLE")
    try:
        value = getter("execution_node", "local")
        if value is None:
            raise HostHardwareInventoryError("EXECUTION_NODE_ID_UNAVAILABLE")
        return validate_uuid(value, field="execution_node_id")
    except HostHardwareInventoryError:
        raise
    except Exception as exc:
        raise HostHardwareInventoryError("EXECUTION_NODE_ID_INVALID") from exc


def _resident_runtime_available(runtime: Any, lifecycle: Any) -> bool:
    instances = getattr(lifecycle, "instances", {})
    instance = instances.get(runtime.id) if isinstance(instances, dict) else None
    if instance is not None:
        state = getattr(instance, "state", None)
        if getattr(instance, "http_reachable", False) and state in {RuntimeState.RUNNING, RuntimeState.EXTERNAL}:
            return True
        if getattr(instance, "process_alive", False) and state in {RuntimeState.STARTING, RuntimeState.RUNNING}:
            return True
    if getattr(runtime, "management", None) is not RuntimeManagement.MANAGED:
        return False
    try:
        managed_executable_file(runtime.executable)
    except (OSError, ValueError, TypeError):
        return False
    return True


def available_runtime_family_ids(model_center: Any) -> frozenset[UUID]:
    runtimes = getattr(model_center, "runtimes", {})
    values = runtimes.values() if isinstance(runtimes, dict) else runtimes
    lifecycle = getattr(model_center, "lifecycle", None)
    families: set[UUID] = set()
    for runtime in sorted(values or (), key=lambda item: str(getattr(item, "id", ""))):
        family = _RUNTIME_FAMILY_IDS.get(getattr(runtime, "runtime_type", None))
        if family is None or lifecycle is None:
            continue
        is_local = getattr(lifecycle, "is_local", None)
        try:
            local = bool(callable(is_local) and is_local(runtime))
        except Exception:
            local = False
        if not local:
            continue
        if _resident_runtime_available(runtime, lifecycle):
            families.add(family)
    return frozenset(families)


def build_host_hardware_snapshot(
    facts: HostHardwareFacts,
    execution_node_identity: Any,
    model_center: Any,
) -> HardwareSnapshot:
    """Pure normalization over supplied Host facts and already-owned state."""
    architecture_id = normalize_architecture(facts.architecture)
    ram_mib = _positive_physical_ram_mib(facts.physical_ram_bytes)
    gpu_vendor_id, vram_mib = _gpu_capability(facts.gpus)
    node_id = _existing_node_id(execution_node_identity)
    return HardwareSnapshot(
        node=ExecutionNodeIdentity(execution_node_id=node_id),
        architecture_id=architecture_id,
        gpu_vendor_id=gpu_vendor_id,
        vram_mib=vram_mib,
        ram_mib=ram_mib,
        runtime_family_ids=available_runtime_family_ids(model_center),
    )


def serialize_host_hardware_snapshot(snapshot: HardwareSnapshot) -> dict[str, Any]:
    """Stable JSON-ready representation; set ordering never leaks into output."""
    return {
        "node": {"execution_node_id": str(snapshot.node.execution_node_id)},
        "architecture_id": str(snapshot.architecture_id),
        "gpu_vendor_id": str(snapshot.gpu_vendor_id) if snapshot.gpu_vendor_id else None,
        "vram_mib": snapshot.vram_mib,
        "ram_mib": snapshot.ram_mib,
        "runtime_family_ids": sorted(str(value) for value in snapshot.runtime_family_ids),
    }


class WindowsHostHardwareProbe:
    """Minimal native Windows probe; no WMI, subprocess, network or persistence."""

    _PCI_VENDOR_PATTERN = re.compile(r"(?:^|\\)VEN_([0-9A-Fa-f]{4})(?:&|$)")

    def collect(self) -> HostHardwareFacts:
        if sys.platform != "win32":
            raise HostHardwareInventoryError("UNSUPPORTED_PLATFORM")
        return HostHardwareFacts(
            architecture=platform.machine(),
            physical_ram_bytes=self._physical_ram_bytes(),
            gpus=self._gpu_facts_fail_closed(),
        )

    @staticmethod
    def _physical_ram_bytes() -> int:
        from ctypes import wintypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query = kernel32.GlobalMemoryStatusEx
        query.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        query.restype = wintypes.BOOL
        if not query(ctypes.byref(status)) or status.ullTotalPhys <= 0:
            raise HostHardwareInventoryError("RAM_FACT_UNAVAILABLE")
        return int(status.ullTotalPhys)

    def _gpu_facts_fail_closed(self) -> tuple[HostGpuFact, ...] | None:
        try:
            adapters = self._physical_display_adapters()
            if len(adapters) != 1:
                return tuple(HostGpuFact(vendor, None) for vendor in adapters)
            vendor = adapters[0]
            values = self._dxgi_dedicated_memory(vendor)
            dedicated = min(values) if values else None
            return (HostGpuFact(vendor, dedicated),)
        except (HostHardwareInventoryError, OSError, ValueError):
            return None

    def _physical_display_adapters(self) -> tuple[int, ...]:
        from ctypes import wintypes

        class DisplayDevice(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128),
                ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128),
                ("DeviceKey", wintypes.WCHAR * 128),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        enumerate_device = user32.EnumDisplayDevicesW
        enumerate_device.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DisplayDevice), wintypes.DWORD]
        enumerate_device.restype = wintypes.BOOL
        adapters: dict[tuple[str, str], int] = {}
        for index in range(256):
            device = DisplayDevice()
            device.cb = ctypes.sizeof(device)
            ctypes.set_last_error(0)
            if not enumerate_device(None, index, ctypes.byref(device), 0):
                error = ctypes.get_last_error()
                if index == 0 and error:
                    raise HostHardwareInventoryError("GPU_FACT_UNAVAILABLE")
                break
            match = self._PCI_VENDOR_PATTERN.search(device.DeviceID)
            if match is None:
                continue
            # One adapter may expose several display heads. The registry adapter
            # key prefix distinguishes physical adapters without leaving this probe.
            adapter_key = device.DeviceKey.rsplit("\\", 1)[0].casefold()
            adapters[(adapter_key, device.DeviceID.casefold())] = int(match.group(1), 16)
        return tuple(value for _, value in sorted(adapters.items()))

    @staticmethod
    def _dxgi_dedicated_memory(vendor_id: int) -> tuple[int, ...]:
        from ctypes import wintypes

        class Guid(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class Luid(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class AdapterDescription(ctypes.Structure):
            _fields_ = [
                ("Description", wintypes.WCHAR * 128),
                ("VendorId", wintypes.UINT),
                ("DeviceId", wintypes.UINT),
                ("SubSysId", wintypes.UINT),
                ("Revision", wintypes.UINT),
                ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t),
                ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", Luid),
                ("Flags", wintypes.UINT),
            ]

        factory = ctypes.c_void_p()
        iid = Guid.from_buffer_copy(UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
        dxgi = ctypes.WinDLL("dxgi", use_last_error=True)
        create_factory = dxgi.CreateDXGIFactory1
        create_factory.argtypes = [ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)]
        create_factory.restype = ctypes.c_long
        if create_factory(ctypes.byref(iid), ctypes.byref(factory)) != 0 or not factory.value:
            raise HostHardwareInventoryError("GPU_FACT_UNAVAILABLE")
        function_type = ctypes.WINFUNCTYPE
        factory_vtable = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        enum_adapters = function_type(
            ctypes.c_long, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)
        )(factory_vtable[12])
        release_factory = function_type(wintypes.ULONG, ctypes.c_void_p)(factory_vtable[2])
        values: list[int] = []
        try:
            for index in range(128):
                adapter = ctypes.c_void_p()
                result = enum_adapters(factory, index, ctypes.byref(adapter))
                if result != 0:
                    if ctypes.c_uint32(result).value != 0x887A0002:
                        raise HostHardwareInventoryError("GPU_FACT_UNAVAILABLE")
                    break
                adapter_vtable = ctypes.cast(adapter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                get_description = function_type(
                    ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(AdapterDescription)
                )(adapter_vtable[10])
                release_adapter = function_type(wintypes.ULONG, ctypes.c_void_p)(adapter_vtable[2])
                try:
                    description = AdapterDescription()
                    if get_description(adapter, ctypes.byref(description)) != 0:
                        raise HostHardwareInventoryError("GPU_FACT_UNAVAILABLE")
                    if not (description.Flags & 2) and description.VendorId == vendor_id:
                        values.append(int(description.DedicatedVideoMemory))
                finally:
                    release_adapter(adapter)
        finally:
            release_factory(factory)
        return tuple(values)


def collect_host_hardware_snapshot(
    execution_node_identity: Any,
    model_center: Any,
    probe: WindowsHostHardwareProbe | None = None,
) -> HardwareSnapshot:
    return build_host_hardware_snapshot(
        (probe or WindowsHostHardwareProbe()).collect(),
        execution_node_identity,
        model_center,
    )
