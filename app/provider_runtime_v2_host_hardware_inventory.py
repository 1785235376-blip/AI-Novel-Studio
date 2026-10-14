"""Host-owned capability facts for the current Provider Runtime execution node."""
from __future__ import annotations

import ctypes
import platform
import sys
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .model_center.domain import RuntimeManagement, RuntimeType
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
    """One physical GPU, with the identity of the adapter that proved it.

    DXGI can expose a single physical GPU as several adapters — an indirect or
    virtual display attached to that GPU does exactly that — so the raw adapter
    identity is kept here rather than collapsed on sight. ``adapter_luid`` and
    ``hardware_id`` are what make an alias **explainable** instead of silently
    deduplicated.
    """

    pci_vendor_id: int
    dedicated_vram_bytes: int | None
    name: str = ""  # Display-only DXGI description; never used to infer vendor or memory.
    device_id: int = 0
    subsystem_id: int = 0
    revision: int = 0
    adapter_luid: str = ""

    @property
    def device_signature(self) -> tuple[int, int, int, int]:
        """What identifies the physical device behind an adapter instance."""
        return (self.pci_vendor_id, self.device_id, self.subsystem_id, self.revision)

    @property
    def hardware_id(self) -> str:
        """The PnP hardware ID of this device, as Windows spells it."""
        return (f"PCI\\VEN_{self.pci_vendor_id:04X}&DEV_{self.device_id:04X}"
                f"&SUBSYS_{self.subsystem_id:08X}&REV_{self.revision:02X}")


@dataclass(frozen=True)
class HostHardwareFacts:
    """Raw local facts. ``gpus=None`` means enumeration was unavailable."""

    architecture: str
    physical_ram_bytes: int
    gpus: tuple[HostGpuFact, ...] | None
    gpu_enumeration: dict[str, Any] | None = None


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


def _host_owned_managed_runtime_available(runtime: Any, lifecycle: Any) -> bool:
    if getattr(runtime, "management", None) is not RuntimeManagement.MANAGED:
        return False
    owned = getattr(lifecycle, "_owned", None)
    if not isinstance(owned, dict):
        return False
    process = owned.get(getattr(runtime, "id", None))
    poll = getattr(process, "poll", None)
    if not callable(poll):
        return False
    try:
        return poll() is None
    except Exception:
        return False


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
        if _host_owned_managed_runtime_available(runtime, lifecycle):
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


def present_display_hardware_ids() -> tuple[str, ...] | None:
    """Hardware IDs of display devices that are present **and started** (passive).

    Uses SetupAPI and cfgmgr32 only: no process is created, nothing is written and
    no network is touched. The result is a **tuple, not a set**, because two
    identical physical GPUs are two present devices and must stay countable — a set
    would collapse them and hide a real second GPU. ``None`` means "could not
    confirm", which callers must treat as unverified rather than as "there are no
    devices"; that distinction is what stops an alias being collapsed on a guess.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Guid(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8),
            ]

        class DeviceInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("ClassGuid", Guid),
                ("DevInst", wintypes.DWORD), ("Reserved", ctypes.c_void_p),
            ]

        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)
        class_guid = Guid.from_buffer_copy(
            UUID("4d36e968-e325-11ce-bfc1-08002be10318").bytes_le  # GUID_DEVCLASS_DISPLAY
        )
        DIGCF_PRESENT = 0x2
        SPDRP_HARDWAREID = 0x1  # 0x0 is SPDRP_DEVICEDESC; reading that yields descriptions
        DN_STARTED = 0x8
        invalid = 0xFFFFFFFFFFFFFFFF
        setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        setupapi.SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(Guid), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD,
        ]
        raw = setupapi.SetupDiGetClassDevsW(ctypes.byref(class_guid), None, None, DIGCF_PRESENT)
        if not raw or raw == invalid:
            return None
        # A c_void_p restype comes back as a Python int; re-wrap it, or a 64-bit
        # handle would be truncated to 32 bits on the way back into the API.
        device_set = ctypes.c_void_p(raw)
        setupapi.SetupDiEnumDeviceInfo.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DeviceInfo),
        ]
        setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
        setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(DeviceInfo), wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
        setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
        cfgmgr32.CM_Get_DevNode_Status.argtypes = [
            ctypes.POINTER(wintypes.ULONG), ctypes.POINTER(wintypes.ULONG),
            wintypes.DWORD, wintypes.ULONG,
        ]
        cfgmgr32.CM_Get_DevNode_Status.restype = wintypes.ULONG
        try:
            found: list[str] = []
            index = 0
            while True:
                info = DeviceInfo()
                info.cbSize = ctypes.sizeof(info)
                if not setupapi.SetupDiEnumDeviceInfo(device_set, index, ctypes.byref(info)):
                    break
                index += 1
                status, problem = wintypes.ULONG(), wintypes.ULONG()
                if cfgmgr32.CM_Get_DevNode_Status(
                    ctypes.byref(status), ctypes.byref(problem), info.DevInst, 0
                ) != 0:
                    continue
                # A ghost or disabled adapter is not a present device.
                if not status.value & DN_STARTED:
                    continue
                needed = wintypes.DWORD()
                setupapi.SetupDiGetDeviceRegistryPropertyW(
                    device_set, ctypes.byref(info), SPDRP_HARDWAREID, None, None, 0,
                    ctypes.byref(needed),
                )
                if not needed.value or needed.value % 2:
                    continue
                buffer = ctypes.create_unicode_buffer(needed.value // 2)
                if not setupapi.SetupDiGetDeviceRegistryPropertyW(
                    device_set, ctypes.byref(info), SPDRP_HARDWAREID, None,
                    ctypes.cast(buffer, ctypes.c_void_p), needed.value,
                    ctypes.byref(needed),
                ):
                    continue
                # Appended, never de-duplicated: two identical GPUs are two devices.
                for value in buffer[: needed.value // 2].split("\x00"):
                    if value:
                        found.append(value.upper())
            return tuple(found)
        finally:
            setupapi.SetupDiDestroyDeviceInfoList(device_set)
    except Exception:
        return None


def resolve_physical_gpus(
    adapters: tuple[HostGpuFact, ...],
    present_hardware_ids: tuple[str, ...] | None,
) -> tuple[tuple[HostGpuFact, ...], dict[str, Any]]:
    """Turn enumerated DXGI adapters into physical devices, and disclose the aliases.

    Adapters sharing a device signature are the same physical device *when the OS
    confirms exactly one present device with that hardware ID*; then — and only
    then — the extras are recorded as aliases and collapsed. Any other outcome
    keeps every adapter, so genuinely multiple identical GPUs stay multiple and an
    unreadable presence inventory fails closed instead of guessing. Nothing is
    dropped silently: the diagnostics record both counts and every LUID.
    """
    groups: dict[tuple[int, int, int, int], list[HostGpuFact]] = {}
    for adapter in adapters:
        groups.setdefault(adapter.device_signature, []).append(adapter)

    devices: list[HostGpuFact] = []
    aliased = 0
    unresolved: list[str] = []
    present_counts: dict[str, int] = {}
    for group in groups.values():
        if len(group) == 1:
            devices.append(group[0])
            continue
        hardware_id = group[0].hardware_id
        present = None if present_hardware_ids is None else sum(
            1 for value in present_hardware_ids if value == hardware_id
        )
        present_counts[hardware_id] = -1 if present is None else present
        if present == 1:
            # Exactly one present device with this signature: the extra adapters
            # are aliases of it, so this is one physical GPU.
            devices.append(group[0])
            aliased += len(group) - 1
        elif present is not None and present >= len(group):
            # The OS confirms at least as many present devices as adapters, so
            # these are genuinely distinct GPUs and every one of them is kept.
            devices.extend(group)
        else:
            # No inventory, or a count that proves neither aliasing nor
            # distinctness: keep every adapter so capability fails closed.
            devices.extend(group)
            unresolved.append(hardware_id)

    diagnostics = {
        "raw_adapter_count": len(adapters),
        "physical_device_count": len(devices),
        "aliased_adapter_count": aliased,
        "presence_verified": present_hardware_ids is not None,
        "present_device_counts": present_counts,
        "unresolved_signatures": sorted(unresolved),
        "adapter_luids": [adapter.adapter_luid for adapter in adapters],
        "hardware_ids": [adapter.hardware_id for adapter in adapters],
    }
    return tuple(devices), diagnostics


class WindowsHostHardwareProbe:
    """Minimal native Windows probe; no WMI, subprocess, network or persistence."""

    _DXGI_ADAPTER_FLAG_SOFTWARE = 2

    def collect(self) -> HostHardwareFacts:
        if sys.platform != "win32":
            raise HostHardwareInventoryError("UNSUPPORTED_PLATFORM")
        gpus: tuple[HostGpuFact, ...] | None = None
        diagnostics: dict[str, Any] | None = None
        try:
            gpus, diagnostics = self._dxgi_gpus_and_diagnostics()
        except Exception:
            gpus, diagnostics = None, None
        return HostHardwareFacts(
            architecture=platform.machine(),
            physical_ram_bytes=self._physical_ram_bytes(),
            gpus=gpus,
            gpu_enumeration=diagnostics,
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
            return self._dxgi_gpu_facts()
        except Exception:
            return None

    @classmethod
    def _fact_from_dxgi_description(
        cls,
        vendor_id: int,
        dedicated_vram_bytes: int,
        flags: int,
        name: str = "",
        *,
        device_id: int = 0,
        subsystem_id: int = 0,
        revision: int = 0,
        adapter_luid: str = "",
    ) -> HostGpuFact | None:
        if flags & cls._DXGI_ADAPTER_FLAG_SOFTWARE:
            return None
        return HostGpuFact(
            vendor_id,
            dedicated_vram_bytes,
            name=str(name).replace("\x00", "")[:128],
            device_id=int(device_id),
            subsystem_id=int(subsystem_id),
            revision=int(revision),
            adapter_luid=str(adapter_luid),
        )

    @classmethod
    def _dxgi_gpus_and_diagnostics(cls) -> tuple[tuple[HostGpuFact, ...], dict[str, Any]]:
        return resolve_physical_gpus(cls._dxgi_raw_adapters(), present_display_hardware_ids())

    @classmethod
    def _dxgi_gpu_facts(cls) -> tuple[HostGpuFact, ...]:
        return cls._dxgi_gpus_and_diagnostics()[0]

    @classmethod
    def _dxgi_raw_adapters(cls) -> tuple[HostGpuFact, ...]:
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
        facts: list[HostGpuFact] = []
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
                    fact = cls._fact_from_dxgi_description(
                        int(description.VendorId),
                        int(description.DedicatedVideoMemory),
                        int(description.Flags),
                        str(description.Description),
                        device_id=int(description.DeviceId),
                        subsystem_id=int(description.SubSysId),
                        revision=int(description.Revision),
                        adapter_luid=(
                            f"{int(description.AdapterLuid.HighPart)}:"
                            f"{int(description.AdapterLuid.LowPart)}"
                        ),
                    )
                    if fact is not None:
                        facts.append(fact)
                finally:
                    release_adapter(adapter)
        finally:
            release_factory(factory)
        return tuple(facts)


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
