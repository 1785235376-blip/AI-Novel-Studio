"""Windows packaging contracts that are additive to the developer runtime."""

from .paths import WindowsPackagingPaths, validate_destructive_target
from .runtime_identity import RuntimeIdentity, RuntimeRole, RuntimeState
from .runtime_lifecycle import RuntimeLifecycle
from .desktop_bridge import PackagedDesktopLifecycle
from .local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from .versioning import ReleaseVersion, VersionMismatch, load_release_version
from .packaged_processes import PackagedProcessConfig, PackagedProcessFactory, PackagedRuntimeLayout

__all__ = [
    "ReleaseVersion",
    "RuntimeIdentity",
    "RuntimeLifecycle",
    "PackagedDesktopLifecycle",
    "RuntimeRole",
    "RuntimeState",
    "LocalSessionBootstrap",
    "TrustedLocalIdentity",
    "VersionMismatch",
    "WindowsPackagingPaths",
    "load_release_version",
    "validate_destructive_target",
    "PackagedProcessConfig",
    "PackagedProcessFactory",
    "PackagedRuntimeLayout",
]
