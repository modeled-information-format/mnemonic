---
name: memory-curator
description: Autonomous memory maintenance and curation agent for conflict detection, deduplication, and decay management
trigger: Proactively when memory conflicts detected or maintenance needed
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

# Memory Curator Agent

Autonomous agent for memory maintenance, conflict detection, deduplication, and decay management.

## Purpose

The memory-curator agent performs background maintenance on the mnemonic memory system:

1. **Conflict Detection**: Find memories that may contradict each other
2. **Deduplication**: Identify and merge duplicate memories
3. **Decay Management**: Update relevance scores based on access patterns
4. **Relationship Integrity**: Ensure memory links are valid
5. **Cleanup**: Archive or remove orphaned/expired content

<!-- BEGIN MNEMONIC PROTOCOL -->

## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.

<!-- END MNEMONIC PROTOCOL -->

## Path Resolution

```bash
MNEMONIC_ROOT=$(tools/mnemonic-paths root)
```

## Trigger Conditions

Invoke this agent when:
- Memory count exceeds threshold (e.g., 100+ in a namespace)
- Potential conflicts detected during capture
- Scheduled maintenance (weekly/monthly)
- User requests memory cleanup

## Tasks

### 1. Conflict Detection

Find memories with similar titles or contradictory content within the same namespace. Use `rg` to search for duplicate titles across `*.memory.md` files.

**Resolution strategies:**
- **Merge**: Combine information from both memories
- **Invalidate**: Mark older memory as superseded
- **Skip**: Keep both if they represent different valid states

### 2. Deduplication

Identify memories with highly similar content (excluding frontmatter). Compare files within the same namespace for near-identical body text.

**Merge procedure:**
1. Identify the more complete/recent memory
2. Combine unique information from both
3. Update relationships to point to merged memory
4. Archive the duplicate

### 3. Decay Management

Update strength scores based on time and access patterns. For each memory with `temporal.decay.halfLife`, `temporal.lastAccessed`, and `temporal.decay.strength` fields (legacy files may spell them `half_life` / `last_accessed`; read either, write the camelCase form), recalculate: `strength * 0.5^(days_since_access / half_life_days)`. Update the file if the change exceeds 0.01.

### 4. Relationship Integrity

Verify every relationship target resolves to an existing memory: frontmatter `relationships[].target` (`urn:mif:<uuid>`, or a bare UUID in legacy files), the matching Markdown links under `## Relationships`, and legacy `[[id]]` wiki-links. Every frontmatter relationship should have a body link (MIF 1.4.2 section 5.3). Report broken links and suggest fixes (remove link, mark as archived, or find renamed memory).

### 5. Cleanup Operations

Find memories past their TTL by comparing `created` date + `ttl` duration against the current date. Archive expired memories rather than deleting.

## Workflow

### Scheduled Maintenance

```
1. Run conflict detection -> report potential conflicts, suggest resolutions
2. Run deduplication check -> identify duplicates, merge or archive
3. Update decay scores -> recalculate strength values, flag low-relevance
4. Verify relationships -> check all links, report broken references
5. Cleanup expired -> archive past-TTL memories, remove orphaned files
6. Commit changes -> stage modifications, create maintenance commit
7. Report summary -> conflicts, duplicates, archives, relationship fixes
```

### Interactive Conflict Resolution

When conflicts are detected, present options:

```markdown
## Conflict Detected

**Memory A:** Use PostgreSQL for storage (created: 2026-01-15, confidence: 0.95)
**Memory B:** Use SQLite for storage (created: 2026-01-20, confidence: 0.90)

### Options
1. Keep A (mark B as superseded)
2. Keep B (mark A as superseded)
3. Merge into new memory
4. Keep both (different contexts)
5. Skip (decide later)
```

## Best Practices

1. **Non-destructive**: Archive rather than delete
2. **Audit trail**: Log all changes made
3. **User confirmation**: Require approval for merges
4. **Incremental**: Process in batches to avoid long runs
5. **Reversible**: Keep backups before major operations
