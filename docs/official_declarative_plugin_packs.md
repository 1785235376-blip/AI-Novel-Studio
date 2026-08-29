# Official Declarative Plugin Packs

Status: **catalog data for Plugin Contract v1**. These packs are not executable tools, not a V1.0 claim, and not a plugin marketplace.

| Field | Value |
|---|---|
| Manifest version | `1.0` |
| Host API version | `1` |
| Execution mode | `declarative` |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| Publisher | unverified metadata, never a signature |
| Release claim | unchanged (`0.7.0 Beta`) |

The runtime Pydantic model in `app/plugin_contracts.py` and `schemas/plugin-manifest-v1.schema.json` remain the only field contracts. These packs add JSON resources under `examples/plugins/`; they do not extend the host API.

## IMPLEMENTED

The current host can do the following with these packs, using the existing Plugin SDK v1:

- Manifest validation
- Discovery under a host-controlled plugins root
- Registration
- Permission review
- Manifest activation (`MANIFEST_ACTIVE` is not code execution)
- Declarative resource validation (path, type, size, SHA-256, JSON parse)
- Declarative catalog read (`GET /api/plugins/{id}/resources`)

## NOT IMPLEMENTED

The following remain disabled or design-only. Official packs must not be described as if they already run:

- Writing preset automatic application
- Workflow execution
- Workflow node execution
- Export execution (`EXPORT PROFILE EXECUTION = NOT IMPLEMENTED`)
- Plugin code execution (Python, JavaScript, Shell, native)
- Provider Plugin
- Blender Plugin
- ComfyUI Plugin
- Plugin Worker
- Capability Broker
- Marketplace
- Plugin signing
- Image or video model calls from pack resources
- Canon / Character / Location / Faction runtime writes from pack templates

If a document, UI string, or pack README ever sounds like these packs are runnable tools, that is a documentation bug.

## Pack catalog

Location: `examples/plugins/<pack-id>/`

| Pack | ID | Capabilities | Resource kinds | What the JSON is for |
|---|---|---|---|---|
| Novel Craft Pack | `novel-craft-pack` | `writing_tool` | writing_presets | Scene Draft, Dialogue Pass, Action Scene, Suspense Build, Emotional Scene, Description Control, POV Lock, Pacing Control |
| Genre Fiction Pack | `genre-fiction-pack` | `writing_tool` | writing_presets | Science Fiction, Fantasy, Mystery, Thriller, Horror, Romance, Historical Fiction |
| Revision Editor Pack | `revision-editor-pack` | `writing_tool`, `workflow` | writing_presets, workflow_templates | Tighten / Expand / polish presets plus Chapter Revision and Developmental Edit templates |
| Continuity Audit Pack | `continuity-audit-pack` | `workflow` | workflow_templates | Character, Timeline, World Rule, Location, Prop, Foreshadowing/Payoff audits |
| Worldbuilding and Character Pack | `worldbuilding-character-pack` | `workflow` | workflow_templates | World Bible, Character, Faction, Location, Character Arc, Relationship builders |
| Screenplay Adaptation Pack | `screenplay-adaptation-pack` | `writing_tool`, `workflow` | writing_presets, workflow_templates | Novel → beat sheet → scene list → outline, plus screen-writing presets |
| Storyboard Planning Pack | `storyboard-planning-pack` | `workflow` | workflow_templates | Shot list, image-prompt, motion-prompt, and transition planning |
| Author Export Profile Pack | `author-export-profile-pack` | `exporter` | export_profiles | Novel Markdown, Manuscript Plain Text, Screenplay Outline JSON, Production Handoff JSON |

The earlier Contract/Validator sample `examples/plugins/story-workflow-pack/` remains a fixture. It is not one of the official packs above.

Every official pack:

- Uses legal SemVer `1.0.0`
- Sets `execution_mode = declarative`
- Declares `requested_permissions = []`
- Contains only JSON resources (plus a README)
- Embeds SHA-256 of the actual resource bytes
- Treats `publisher` as unverified display metadata
- Does not ship scripts, binaries, symlinks, or executable entrypoints

## Resource semantics

JSON inside a pack is **data**. Consumers must not render it as HTML, follow URLs, or evaluate strings.

Writing presets describe purpose, recommended controls, writing goals, constraints, checklist, and optional parameter hints. They are not prompt injectors and the host does not apply them.

Workflow templates describe ordered manual stages. Continuity templates collect, compare, classify, and require human review. They do not modify novel data and they do not bypass future Canon / Revision / permission systems.

Worldbuilding templates use stable field names such as `character.role`, `world.rules`, `faction.purpose`, and `location.geography` so a later runtime can bind them to first-class domain objects. That binding is not implemented in this drop.

Export profiles declare format, intended use, section ordering, metadata inclusion, naming convention, structural options, and compatibility notes. **EXPORT PROFILE EXECUTION = NOT IMPLEMENTED.**

Storyboard templates prepare shot, image-prompt, motion-prompt, and transition intent. They do not generate media or register providers.

Genre presets use abstract narrative style. They must not instruct the host or a writer to imitate a living author.

## How to install a pack for discovery

Copy a pack directory to the host-controlled plugins root (`<data_path>/plugins/<pack-id>/`) so `manifest.json` is one level below that root. Discovery never scans `examples/plugins` by itself.

Then the existing register → permission review → enable → catalog-read path applies. Enable still means **manifest activation**, not execution.

## Related documents

- [plugin_sdk_v1.md](plugin_sdk_v1.md) — contract and validator
- [plugin_security_model.md](plugin_security_model.md) — path, hash, and fail-closed rules
- [plugin_worker_runtime_design.md](plugin_worker_runtime_design.md) — design-only worker, not implemented
