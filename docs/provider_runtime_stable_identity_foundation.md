# Provider Runtime Stable Identity Foundation

The existing owner boundaries remain authoritative:

- Providers are owned by `app.model_runtime.ProviderRegistry` and its `ProviderDescriptor` entries.
- Text models are owned by `app.model_runtime.ModelRegistry`; Model Center catalog models are owned by `app.model_center.service.ModelCenterService` and `ModelDefinition`.
- Durable Model Center runtimes are owned by `ModelCenterService` and `RuntimeDefinition`.
- The packaged process runtime identity in `app.packaging.runtime_identity` remains process/ownership metadata. The local execution-node UUID is separately owned by `ExecutionNodeIdentityStore`.

`app.stable_identity.StableIdentityStore` persists opaque UUIDs using the existing `atomic_write` convention. IDs are generated only when an owner creates or backfills an entity, never from slugs, names, paths, endpoints, hosts, or hashes. Malformed, zero, duplicate, or conflicting identities fail closed. Ordinary updates retain the stored identity, and caller-supplied IDs are ignored on create and rejected on mutation.

AUTHORITATIVE ENTITY KEY RENAME = NOT SUPPORTED IN THIS FOUNDATION. Provider, model, and runtime keys are immutable; display and configuration properties may change without changing the UUID. Deleting an entity and later creating the same key represents a new entity and receives a new UUID.

Built-in runtime-family, architecture, and GPU-vendor IDs are explicit constants in `app.stable_identity`; they are not generated at lookup time. This foundation does not perform routing, authorization, credential resolution, provider HTTP, model execution, runtime lifecycle actions, or hardware probing.
