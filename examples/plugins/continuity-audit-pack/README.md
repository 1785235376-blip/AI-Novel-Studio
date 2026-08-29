# continuity-audit-pack

Official **declarative** plugin pack for Plugin Contract v1. This is catalog data, not an executable tool.

## Purpose

Read-only continuity audit templates for character, timeline, world rules, location, props, and foreshadowing/payoff.

## Resources

- workflow_templates: character-continuity-audit, timeline-audit, world-rule-audit, location-continuity-audit, prop-continuity-audit, foreshadowing-payoff-audit

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
