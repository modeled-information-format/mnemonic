# MIF Level 3 Schema

mnemonic's profile of the Modeled Information Format (MIF) 1.4.2. The
normative specification is <https://mif-spec.dev>. Concept frontmatter keys
are camelCase (MIF 1.4.2 section 3.3); legacy snake_case keys written by
older mnemonic releases are still read.

## Minimal Required Fields

```yaml
---
id: 550e8400-e29b-41d4-a716-446655440000
title: "Human-readable title"
type: semantic|episodic|procedural
created: 2026-01-23T10:30:00Z
---
```

## Full Schema (All Optional Fields)

```yaml
---
id: 550e8400-e29b-41d4-a716-446655440000
type: semantic|episodic|procedural
namespace: _semantic/decisions/project
created: 2026-01-23T10:30:00Z
modified: 2026-01-23T14:22:00Z
title: "Human-readable title"
tags:
  - tag1
  - tag2

# Bi-temporal tracking (optional)
temporal:
  validFrom: 2026-01-23T00:00:00Z
  validUntil: null
  recordedAt: 2026-01-23T10:30:00Z
  ttl: P90D
  decay:
    model: exponential
    halfLife: P7D
    strength: 0.85
  accessCount: 5
  lastAccessed: 2026-01-23T14:22:00Z

# Provenance (optional)
provenance:
  sourceType: user_explicit | user_implicit | agent_inferred | external_import | system_generated
  sourceRef: file:///path/to/source.ts:42
  agent: claude-opus-4
  confidence: 0.95
  sessionId: abc123

# Code structure awareness (optional)
codeRefs:
  - file: src/auth/handler.ts
    line: 42
    symbol: authenticateUser
    type: function

# Citations - external references (optional, MIF 1.4.2 section 5.4)
citations:
  - "@type": Citation
    citationType: documentation
    citationRole: supports
    title: "Source Title"
    url: https://example.com/source
    accessed: 2026-01-23
    relevance: 0.90

# Conflict tracking (optional, mnemonic extension)
conflicts:
  - memoryId: xyz789
    resolution: merged
    resolvedAt: 2026-01-23T12:00:00Z

# Relationships - links to related memories (optional)
# kebab-case type, urn:mif:<uuid> target, optional metadata.label
relationships:
  - type: relates-to
    target: urn:mif:a5e46807-6883-4fb2-be45-09872ae1a994
    metadata:
      label: "Optional human-readable description"
  - type: supersedes
    target: urn:mif:b6f57918-7994-4dc3-af56-10983bf2b005
  - type: derived-from
    target: urn:mif:c7e68a29-8aa5-4bd4-9d67-21a94c03c116
---

# Title

Content.

## Relationships

- relates-to [Related Memory](urn:mif:a5e46807-6883-4fb2-be45-09872ae1a994)
- supersedes [Older Memory](urn:mif:b6f57918-7994-4dc3-af56-10983bf2b005)
- derived-from [Source Memory](urn:mif:c7e68a29-8aa5-4bd4-9d67-21a94c03c116)
```

Every frontmatter relationship MUST also appear as a Markdown link under
`## Relationships` (MIF 1.4.2 section 5.3); the body line carries the same
type and target as the frontmatter entry.

## Directory Structure

**Unified structure** (`${MNEMONIC_ROOT}/`):
```
${MNEMONIC_ROOT}/
├── {org}/                     # Organization-level
│   ├── _semantic/             # Org-wide facts/knowledge
│   │   ├── decisions/
│   │   ├── knowledge/
│   │   └── entities/
│   ├── _episodic/             # Org-wide events
│   │   ├── incidents/
│   │   ├── sessions/
│   │   └── blockers/
│   ├── _procedural/           # Org-wide procedures
│   │   ├── runbooks/
│   │   ├── patterns/
│   │   └── migrations/
│   └── {project}/             # Project-specific memories
│       ├── _semantic/
│       │   ├── decisions/
│       │   ├── knowledge/
│       │   └── entities/
│       ├── _episodic/
│       │   ├── incidents/
│       │   ├── sessions/
│       │   └── blockers/
│       ├── _procedural/
│       │   ├── runbooks/
│       │   ├── patterns/
│       │   └── migrations/
│       └── .blackboard/
├── _semantic/knowledge/
├── _procedural/patterns/
├── _episodic/sessions/
└── .blackboard/
```
