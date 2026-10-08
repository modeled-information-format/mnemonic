---
title: "MIF Level 3 Format"
description: "Adopt Modeled Information Format Level 3 for memory file structure"
type: adr
category: architecture
tags:
  - format
  - mif
  - yaml
  - metadata
  - temporal
status: accepted
created: 2026-01-24
updated: 2026-10-08
author: zircote
project: mnemonic
technologies:
  - yaml
  - markdown
  - mif
audience:
  - developers
  - architects
related:
  - adr-001-filesystem-based-storage.md
---

# ADR-002: MIF Level 3 Format

## Status

Accepted

## Context

### Background and Problem Statement

Mnemonic needs a standardized format for memory files that supports structured metadata while remaining human-readable. The format must enable temporal awareness, provenance tracking, and interoperability with other AI systems.

### Current Limitations

Without a standardized format:
- No consistent structure for metadata
- Cannot track when information is valid vs. when it was recorded
- No way to express confidence or source
- Limited interoperability with other tools

## Decision Drivers

### Primary Decision Drivers

1. **Structured Metadata**: Must support type, timestamps, tags in consistent structure
2. **Temporal Awareness**: Must distinguish validity periods from recording time
3. **Provenance Tracking**: Must track source and confidence level
4. **Structured Format**: Must support structured metadata for search and relationship tracking

### Secondary Decision Drivers

1. **Extensibility**: Additional fields without breaking compatibility
2. **Human Readability**: Developers should understand the format
3. **Tool Support**: Should work with existing YAML/markdown tools

## Considered Options

### Option 1: Custom JSON Schema

**Description**: Define a custom JSON schema for memory structure.

**Technical Characteristics**:
- Strict schema validation
- JSON format throughout
- Custom field definitions

**Advantages**:
- Precise validation
- Machine-readable
- Flexible structure

**Disadvantages**:
- Not human-friendly for content
- No standard for AI memories
- Would need to build ecosystem from scratch

**Risk Assessment**:
- **Technical Risk**: Medium. Custom schema needs maintenance.
- **Adoption Risk**: High. No existing ecosystem.
- **Usability Risk**: High. JSON poor for prose content.

### Option 2: Simple YAML Frontmatter

**Description**: Use minimal YAML frontmatter with basic fields.

**Technical Characteristics**:
- Simple key-value pairs
- Markdown body for content
- Minimal required fields

**Advantages**:
- Easy to learn
- Minimal overhead
- Quick to implement

**Disadvantages**:
- No temporal modeling
- No provenance tracking
- Limited future extensibility
- No interoperability standard

**Risk Assessment**:
- **Technical Risk**: Low. Simple to implement.
- **Feature Risk**: High. Missing critical capabilities.
- **Future Risk**: High. Hard to add features later.

### Option 3: MIF Level 3 Specification

**Description**: Adopt the Modeled Information Format Level 3 standard.

**Technical Characteristics**:
- Standardized YAML frontmatter
- Bi-temporal tracking (valid time vs. recorded time)
- Decay modeling for relevance
- Cognitive type classification
- Provenance with confidence scores

**Advantages**:
- Industry-proposed standard for AI memories
- Comprehensive metadata model
- Designed for interoperability
- Extensible without breaking changes
- Supports advanced features (decay, confidence)

**Disadvantages**:
- More fields to manage
- Learning curve for users
- Requires validation

**Risk Assessment**:
- **Technical Risk**: Low. Specification is well-defined.
- **Adoption Risk**: Low. Following a standard.
- **Complexity Risk**: Medium. More fields than minimal approach.

## Decision

We will adopt the Modeled Information Format (MIF) Level 3 specification.

### Format Structure

```yaml
---
id: UUID
type: semantic|episodic|procedural
namespace: category/scope
created: ISO-8601
modified: ISO-8601
title: "Human-readable title"
tags: [list, of, tags]

temporal:
  valid_from: ISO-8601
  valid_until: ISO-8601 (optional)
  recorded_at: ISO-8601
  decay:
    model: exponential
    half_life: P7D
    strength: 0.0-1.0

provenance:
  source_type: user_explicit|inferred|conversation
  agent: model-identifier
  confidence: 0.0-1.0
---

# Title

Markdown content...
```

### Key Features

- **Bi-temporal tracking**: Separates "when it's valid" from "when it was recorded"
- **Decay modeling**: Configurable relevance decay over time
- **Cognitive types**: Semantic (facts), episodic (events), procedural (how-tos)
- **Provenance**: Tracks source and confidence level

## Consequences

### Positive

1. **Standardized**: Following a specification ensures consistency across implementations
2. **Structured Format**: MIF supports structured metadata and relationships
3. **Rich Metadata**: Temporal and provenance data enable intelligent retrieval
4. **Extensible**: Additional fields can be added without breaking compatibility

### Negative

1. **Complexity**: More fields to manage than simple key-value storage
2. **Learning Curve**: Users and tools must understand the format
3. **Validation Needed**: Invalid frontmatter could cause parsing issues

### Neutral

1. **File Size**: Slightly larger files due to metadata
2. **Processing**: Additional parsing for metadata extraction

## Decision Outcome

MIF Level 3 adoption achieves our primary objectives:
- Comprehensive structured metadata
- Full bi-temporal tracking
- Provenance and confidence scoring
- Structured metadata and relationships

Mitigations for negative consequences:
- Provide templates and skills for correct format generation
- Validate frontmatter in hooks before commit
- Document format thoroughly with examples
- Provide migration tools for format updates

## Related Decisions

- [ADR-001: Filesystem-based Storage](adr-001-filesystem-based-storage.md) - Storage mechanism for MIF files

## Links

- [MIF Specification](https://mif-spec.dev) - Modeled Information Format specification
- [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) - Date/time format standard
- [ISO 8601 Durations](https://en.wikipedia.org/wiki/ISO_8601#Durations) - Duration format for decay half-life

## More Information

- **Date:** 2026-01-24
- **Source:** MIF specification adoption decision
- **Related ADRs:** ADR-001

## Audit

### 2026-01-24

**Status:** Compliant

**Findings:**

| Finding | Files | Lines | Assessment |
|---------|-------|-------|------------|
| MIF Level 3 frontmatter template | `skills/core/SKILL.md` | L346-L394 | compliant |
| Cognitive type classification | `skills/core/SKILL.md` | L143-L149 | compliant |
| Temporal fields in capture | `commands/capture.md` | L99-L116 | compliant |
| Provenance tracking | `commands/capture.md` | L112-L115 | compliant |
| Decay model support | `skills/format/SKILL.md` | L1-L50 | compliant |

**Summary:** MIF Level 3 format implementation follows specification.

**Action Required:** None

### 2026-10-08

**Status:** Accepted (amended for MIF 1.4.1)

**Findings:** "MIF" expands to *Modeled Information Format*; earlier text
said "Memory Interchange Format" and has been corrected. MIF 1.4.1 (section
3.3) spells concept frontmatter keys in camelCase, so the format structure
above is now written as `validFrom`, `recordedAt`, `decay.halfLife`,
`provenance.sourceType` (values `user_explicit`, `user_implicit`,
`agent_inferred`, `external_import`, `system_generated`). Relationship types
are kebab-case tokens (`relates-to`), targets are `urn:mif:<uuid>`, and each
relationship is mirrored as a Markdown link under `## Relationships`. The
snake_case spellings shown in *Format Structure* remain readable for
memories written before this change.

**Action Required:** None. Writers emit the 1.4.1 forms; readers accept
both; `tools/mnemonic-migrate-mif` upgrades legacy files on request.
