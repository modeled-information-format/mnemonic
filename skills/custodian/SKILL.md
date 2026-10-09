---
name: custodian
description: |
  Memory system custodian for health checks, validation, and maintenance.
  Trigger phrases: "check memory health", "validate memories", "fix broken links",
  "update decay", "relocate memories", "audit memories", "memory maintenance",
  "custodian", "memory health"
user-invocable: true
allowed-tools:
- Bash
- Read
- Write
- Glob
- Grep
- Task
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# Custodian Skill

Provides custodial services for the mnemonic memory system: auditing, validation, link repair, decay management, relocation, and summarization.

## When to Use

- **Proactively** when session_start reports low health scores or potential duplicates
- **On request** when user asks about memory health, broken links, or maintenance
- **After project renames** to relocate memories and update references
- **Periodically** to keep decay scores current and identify orphaned memories

## Architecture

The custodian operates through focused Python modules:

| Module | Responsibility |
|--------|---------------|
| `memory_file.py` | Parse/validate/update MIF frontmatter |
| `link_checker.py` | Build UUID/slug index, validate links, find orphans |
| `decay.py` | Calculate exponential/linear/step decay, update strength |
| `relocator.py` | Move files + update all cross-references |
| `validators.py` | MIF schema validation, ontology relationship checks |
| `report.py` | Structured findings with markdown/JSON output |
| `custodian.py` | CLI orchestrator dispatching to modules |

## Subcommands

### audit (default)

Runs all checks in a single pass. This is the recommended entry point.

```
/mnemonic:custodian audit [--fix] [--dry-run]
```

Checks performed:
1. **Frontmatter**: Required fields, UUID format, type enum, date format
2. **Links**: Wiki-links resolve to existing memories
3. **Relationships**: Types match MIF built-in or ontology-defined types
4. **Decay**: Recalculates strength values using configured model
5. **Orphans**: Detects memories with no incoming references

### relocate

Moves memories when project or org names change:

```
/mnemonic:custodian relocate <old-path> <new-path> [--dry-run]
```

1. Builds link index across all memory roots
2. Updates path references in ALL memory files (not just relocated ones)
3. Moves files using `git mv` for history preservation
4. Cleans up empty directories

### validate-links

```
/mnemonic:custodian validate-links [--fix]
```

With `--fix`: broken `[[wiki-links]]` are replaced with plain text.

### decay

```
/mnemonic:custodian decay [--dry-run]
```

Updates `temporal.decay.currentStrength` (or `strength`) in-place.
Formula: `strength * 0.5^(days_since_access / half_life_days)`

### summarize

```
/mnemonic:custodian summarize
```

Identifies compression candidates (>100 lines, >30d old or strength < 0.3).
Delegate actual compression to `mnemonic:compression-worker` agent.

### ensure-bidirectional

```
/mnemonic:custodian ensure-bidirectional [--fix]
```

Scans all memory relationships and checks that each has a corresponding inverse
back-reference in the target. For example, if A `supersedes` B, B should have
`superseded-by` pointing back to A. Legacy spellings (`SupersededBy`,
`superseded_by`) and bare-UUID targets count as present; new back-references
are written in MIF 1.4.2 form (kebab-case type, `urn:mif:<uuid>` target, plus a
body `## Relationships` link).

Without `--fix`: reports missing back-references as warnings.
With `--fix`: auto-creates the missing inverse relationships.

### validate-memories / validate-relationships

Read-only validation. Reports errors without modifying files.

## Integration

- **Complements gc**: GC handles cleanup/archival; custodian handles validation/repair
- **Complements memory-curator**: Curator handles conflicts/deduplication; custodian handles schema/links/decay
- **Uses PathResolver**: Centralized path resolution from `lib/paths.py`
- **Uses compression-worker**: Delegates summarization to existing agent

## Key Design Decisions

- **Non-destructive by default**: `--dry-run` support on all mutation operations
- **Atomic writes**: All file modifications use temp file + replace pattern
- **Git integration**: `--commit` flag for committing changes
- **Functional modules**: Lightweight functions over heavy OOP, matching codebase style
- **Single-pass audit**: All checks run once per file for efficiency
