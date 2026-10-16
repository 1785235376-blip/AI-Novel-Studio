# Local Interop V1 compatibility

| Item | V1 contract |
| --- | --- |
| Protocol name | PoemSeed Local Interop |
| Protocol version | 1.0 |
| Studio identity | poemseed.creative.studio |
| Tutor identity | poemseed.tutor.desktop |
| Studio software version | 0.7.0 development baseline plus interop branch |
| Tutor cloud/reference software version | 0.1.0 development baseline plus interop branch |
| Real tutor desktop minimum | LOCAL_REQUIRED; no desktop version certified |
| Development transport | Explicit configured 127.0.0.1 HTTP only |
| Windows transport | Current-user Named Pipe reference; desktop wiring LOCAL_REQUIRED |
| Feature default | OFF in both products |
| V1 acceptance mode | Forced OFF |
| Required support | Product/protocol identity, handshake, explicit capability intersection |
| Optional support | Individual context/guidance/diagnostic/model/verifier/case/handoff capabilities |
| Deprecated fields | None in 1.0 |

Product software versions are not protocol versions. UI rebranding does not change
stable product identity, capability strings, schema IDs or action semantics. URI
schemes are UI registration details and are not protocol identities.

The experimental branch is a review candidate. A peer declaring protocol 1.0 must
still pass strict validation and trusted local authorization; advertised product
version or role alone is insufficient. Unknown versions fail explicitly. Optional
capability absence produces CAPABILITY_NOT_SUPPORTED and leaves normal app use
unchanged. V1.5 may extend metadata/recommendation/diagnostic/verifier/case surfaces;
V2 broker/scheduler/ecosystem changes are not implemented here. In particular,
cross-product model execution remains prohibited.
