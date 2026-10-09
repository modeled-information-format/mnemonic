---
id: 550e8400-e29b-41d4-a716-446655440141
type: semantic
namespace: decisions/project
created: 2026-10-08T10:30:00Z
title: "Use PostgreSQL for Storage (MIF 1.4.2 form)"
modified: 2026-10-08T14:22:00Z
tags:
  - architecture
  - database
temporal:
  validFrom: 2026-10-08T00:00:00Z
  recordedAt: 2026-10-08T10:30:00Z
  lastAccessed: 2026-10-08T10:30:00Z
  decay:
    model: exponential
    halfLife: P90D
    strength: 1.0
provenance:
  sourceType: user_explicit
  agent: claude-opus-4
  confidence: 0.95
relationships:
  - type: relates-to
    target: urn:mif:550e8400-e29b-41d4-a716-446655440001
    metadata:
      label: "Earlier storage decision"
citations:
  - "@type": Citation
    citationType: documentation
    citationRole: supports
    title: "PostgreSQL documentation"
    url: https://www.postgresql.org/docs/
summary: "Chose PostgreSQL for ACID compliance and JSON support."
compressedAt: 2026-10-08T12:00:00Z
---

# Use PostgreSQL for Storage

We decided to use PostgreSQL as our primary database.

## Relationships

- relates-to [Use PostgreSQL for Storage](urn:mif:550e8400-e29b-41d4-a716-446655440001)
