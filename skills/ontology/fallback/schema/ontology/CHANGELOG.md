# Ontology Schema Changelog

All notable changes to the ontology schema are documented in this file.

## [MIF 1.4.2] - 2026-10-08

### Changed
- Provenance only: `ontology.schema.json` and `ontology.context.jsonld` were
  checked byte-identical to <https://mif-spec.dev/schema/1.4.2/ontology/>
  (MIF 1.4.2, release commit `ad520b8c`). File contents are unchanged.

## [MIF 1.4.2] - 2026-10-08

### Changed
- Re-vendored `ontology.schema.json` and `ontology.context.jsonld` verbatim
  from MIF 1.4.2 (`public/schema/1.4.2/ontology/`). The previous copies were
  local edits that matched no MIF release.
- JSON-LD context vocabulary moved to `https://mif-spec.dev/ns/ontology#`
  (`mif:` prefix is now `https://mif-spec.dev/ns/`).

### Added (from MIF)
- `ontology.extends`, entity-type `subtype_of`, `aliases`, `exemplars`,
  `negative_examples`, and a unified discovery `patterns` array.

Both bundled ontologies (`mif-base`, `software-engineering`) validate against
the new schema unchanged.

## [v2] - 2026-01-27

### Added
- `content_patterns` array for base ontology namespace suggestion
- `file_patterns` array for file-based namespace suggestion
- `contentPattern` definition for content matching
- `filePattern` definition with namespaces array and context field

### Changed
- Made `suggest_entity` optional in `discoveryPattern` (was required)
- Updated namespace path examples to use underscore prefix (`_semantic/decisions`)

## [v1] - 2026-01-26

### Added
- Initial cognitive triad namespace hierarchy
- Entity type definitions with base types (semantic, episodic, procedural)
- Trait/mixin system
- Relationship definitions
- Discovery pattern support for entity suggestion
