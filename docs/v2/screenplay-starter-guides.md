# Independent screenplay starter guides

GET `/api/novels/{nid}/experimental/creative/screenplay-presets` and the `/api/v1`
alias require original domain.read authority plus narrative_production_v2 with
V1 acceptance disabled. The fixed response is `{schema_version:1,templates:[...]}`;
rows have id, version, title, description and an original CreativeDocumentIn
prototype. Version 1 contains FEATURE_FILM, SHORT_FILM, ANIMATION, ADVERTISEMENT.
Catalog versioning is immutable guide-content identity, not a document revision.

Reading, opening, changing a selection and previewing never save content or invoke
models. An explicit use action creates a new independent unsaved local screenplay,
with fresh scene IDs and no source chapters. Existing draft/permission guards
prevent overwriting dirty, uncertain, busy or revoked content. Explicit Save uses
the existing document APIs and revisions; guides add no persistent metadata or
second storage. Author edits are ordinary screenplay content, not a tracked live
link to a template. Catalog failures preserve the current draft and allow retry.

The shared UI primitives and existing content slot are reused without shell or
visual-system changes. The guides are original writing prompts to replace, not
finished fiction or guaranteed professional formats. Game branching, real model
quality, professional pagination and future PDF support remain separate work.
