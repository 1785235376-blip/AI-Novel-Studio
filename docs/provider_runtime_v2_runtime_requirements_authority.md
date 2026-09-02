# Provider Runtime 2.1B Runtime Requirements Authority

Model Center `RuntimeDefinition` and its typed runtime profiles own the
explicit runtime architecture requirement. `architecture_id` is optional and,
when present, must be a non-zero UUID from the Stable Identity architecture
taxonomy. It persists through the existing trusted runtime configuration and
reload path without conversion to a free-form architecture name.

The value describes what a configured runtime profile requires or supports. It
does not describe the current Host's hardware inventory. No host architecture,
processor, RAM, VRAM, GPU, CUDA, WMI, subprocess, or platform probe is used.
Runtime type and operating system do not provide defaults. The built-in
`llama-cpp-local` and `comfyui-local` definitions remain unpopulated until a
trusted packaged/runtime configuration supplies an explicit requirement.

The Model Center Snapshot Bridge remains a read-only consumer. A known
architecture UUID is copied exactly into Provider Runtime
`RuntimeRequirements`; a missing value yields
`MISSING_REQUIRED_HARDWARE_FACT`, and malformed, zero, unknown, or wrong-kind
taxonomy values are rejected. Snapshot callers cannot provide an architecture
override. Authorization, trust, compatibility, location, credentials, routing
policy, and execution semantics are unchanged.
