"""Internal Desktop Integration SDK. V1 wire models stay in local_interop_protocol.

All native desktop installations, signed evidence and real two-product wiring
remain LOCAL_REQUIRED until measured in their actual environment. Imports and
constructors never enable a bridge, launch software, or authorize content.
"""

from .diagnostics import (
    AuditRecord,
    HealthStatus,
    InteropAudit,
    InteropDiagnosticSnapshot,
    InteropHealth,
)
from .events import (
    EventDelivery,
    EventProvenance,
    InteropEventSource,
    InteropEventSourceRegistry,
)
from .identity import (
    AttestationState,
    DiscoveredPeer,
    InstallationRecord,
    InteropPeerAttestation,
    InteropPeerDiscovery,
    InteropPeerTrustStore,
    MockPeerAttestation,
    PeerIdentity,
    PeerOSFacts,
    ProductionPeerAttestation,
    TrustRecord,
)
from .lifecycle import InteropLifecycleCoordinator, ShutdownReport
from .providers import (
    InteropCaseGateAdapter,
    InteropContextProvider,
    InteropHandoffHandler,
    InteropMemoryCandidateAdapter,
    InteropModelRegistryCache,
    InteropModelRegistryProvider,
    InteropNotificationAdapter,
    InteropTutorAdapter,
    InteropVerifierAdapter,
    ModelRegistryCacheSnapshot,
    UserPresenceGate,
)
from .transport import (
    DesktopTransportAdapter,
    InteropTransport,
    TransportSnapshot,
    TransportState,
)

__all__ = [
    "AttestationState",
    "AuditRecord",
    "DesktopTransportAdapter",
    "DiscoveredPeer",
    "EventDelivery",
    "EventProvenance",
    "HealthStatus",
    "InstallationRecord",
    "InteropAudit",
    "InteropCaseGateAdapter",
    "InteropContextProvider",
    "InteropDiagnosticSnapshot",
    "InteropEventSource",
    "InteropEventSourceRegistry",
    "InteropHandoffHandler",
    "InteropHealth",
    "InteropLifecycleCoordinator",
    "InteropMemoryCandidateAdapter",
    "InteropModelRegistryCache",
    "InteropModelRegistryProvider",
    "InteropNotificationAdapter",
    "InteropPeerAttestation",
    "InteropPeerDiscovery",
    "InteropPeerTrustStore",
    "InteropTransport",
    "InteropTutorAdapter",
    "InteropVerifierAdapter",
    "MockPeerAttestation",
    "ModelRegistryCacheSnapshot",
    "PeerIdentity",
    "PeerOSFacts",
    "ProductionPeerAttestation",
    "ShutdownReport",
    "TransportSnapshot",
    "TransportState",
    "TrustRecord",
    "UserPresenceGate",
]
