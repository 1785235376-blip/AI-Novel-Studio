# Local Interop V1 context and evidence

AppContextCapsule records immutable capsule ID, source version and `capsule_hash`;
product/version/instance; project/version/workspace/storyline/branch; module and
surface; chapter/version; selection ID/hash; task ID/type/status; runtime/model;
error code; privacy scope; creation/expiry and evidence. Unavailable metadata remains null; no values are guessed. Canonical serialization
hydrates defaults before hashing. Content defaults to NONE.

| Level | Content | Consent |
| --- | --- | --- |
| 0 / NONE | Structured metadata only | Preview confirmation before request |
| 1 / SELECTED_TEXT | Exact saved-source selection | Explicit selection checkbox and preview |
| 2 / CURRENT_CHAPTER | Exact current chapter | Explicit chapter checkbox and preview |
| 3 / PROJECT_CONTEXT | Specifically selected context | Explicit resource/scope selection |

A UI selection must be tied to its saved source. Chapter or project changes
between preview and send produce SOURCE_CHANGED/CONTEXT_STALE. Capsules are
immutable snapshots; a new state creates a new ID/hash. Validation rejects stale
versions, replay where freshness is required, invalid expiry/hash and unauthorized
source content. No capsule locator is automatically fetched.

ContextEvidence contains source ID/version, opaque locator, content hash,
timestamp, authority and privacy. AUTHORITATIVE, CONSTRAINING, SUPPORTING and
ADVISORY describe trusted source roles, not arbitrary caller preferences. Studio
FAILED remains authoritative even when advice says SUCCESS. The adapter maps
values to the existing Context V2 contract and retains host source provenance.

Privacy is inherited from every source, including capsule privacy even if evidence
is empty. The ordered policy is LOCAL_ONLY, REDACTION_REQUIRED, CONSENTED_CLOUD
from most to least restrictive. Interop defaults local and does not create cloud
consent. A derived object cannot weaken privacy through a text summary.

Events cover project/chapter lifecycle, task lifecycle, model/runtime change,
validation, export error and workflow blocking. Event payloads are metadata only,
with content NONE. Bounded subscriber queues coalesce high-frequency state;
live authorization is checked before each delivery. Revoke, scope/membership
change, project switch and bridge disable terminate affected subscriptions.
