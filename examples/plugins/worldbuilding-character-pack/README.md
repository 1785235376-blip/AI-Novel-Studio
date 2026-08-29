# worldbuilding-character-pack

Official **declarative** plugin pack for Plugin Contract v1. This is catalog data, not an executable tool.

## Purpose

Declarative world, character, faction, location, arc, and relationship builders with stable field names.

## Resources

- workflow_templates: world-bible-builder, character-builder, faction-builder, location-builder, character-arc-planner, relationship-planner

## What this pack does

- Ships a Contract v1 `manifest.json`
- Declares JSON resources with live SHA-256 hashes
- Can be discovered, registered, permission-reviewed, and catalog-read

## What this pack does not do

- Does **not** execute writing presets, workflows, or export profiles
- Does **not** contain Python, JavaScript, Shell, or any executable entrypoint
- Does **not** request `network`, `process`, `filesystem.write`, or `model.*` permissions
- Does **not** register Providers, call image/video models, or write novel data
- `publisher` is unverified metadata, not a signature or trusted identity

Current host state remains:

- `execution_mode = declarative`
- `execution_supported = false`
- `isolation = DENY_ALL`
