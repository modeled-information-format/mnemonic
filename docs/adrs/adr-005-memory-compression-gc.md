---
title: "Memory Compression via GC Extension"
description: "Extend gc command with compression flags using haiku agent for summarization"
type: adr
category: architecture
tags:
  - compression
  - gc
  - summarization
  - maintenance
status: accepted
created: 2026-01-24
updated: 2026-10-08
author: zircote
project: mnemonic
technologies:
  - bash
  - haiku
  - yaml
audience:
  - developers
  - architects
related:
  - adr-002-mif-level-3-format.md
---

# ADR-005: Memory Compression via GC Extension

## Status

Accepted

## Context

### Background and Problem Statement

As the mnemonic system accumulates memories over time, some older or lower-value memories may become verbose while remaining useful for context. We need a mechanism to compress these memories while preserving their essential information.

### Current State

The existing `/mnemonic:gc` command handles memory garbage collection:
- Identifies old memories by age
- Identifies expired TTL memories
- Identifies low-strength memories
- Archives or deletes candidates

However, there's no mechanism to compress memories that should be retained but are unnecessarily verbose.

## Decision Drivers

### Primary Decision Drivers

1. **Storage Efficiency**: Reduce storage footprint of older memories
2. **Context Conservation**: Preserve essential information in compressed form
3. **Natural Integration**: Fit into existing maintenance workflow
4. **Quality Summaries**: Use AI for intelligent compression

### Secondary Decision Drivers

1. **Reversibility**: Compression should be trackable (not destructive)
2. **Selective**: Only compress when beneficial
3. **Cost Efficiency**: Use cheap model for summarization

## Considered Options

### Option 1: Standalone Compress Command

**Description**: Create a new `/mnemonic:compress` command separate from gc.

**Technical Characteristics**:
- New command file
- Separate workflow from gc
- Manual invocation

**Advantages**:
- Clear single responsibility
- No changes to existing gc
- Explicit user control

**Disadvantages**:
- Another command to remember
- Separate from maintenance workflow
- May be forgotten

**Risk Assessment**:
- **Adoption Risk**: Medium. Users may not invoke regularly.
- **Integration Risk**: Medium. Separate from gc workflow.

### Option 2: Extend GC Command (Selected)

**Description**: Add compression as an optional step in gc workflow.

**Technical Characteristics**:
- New flags: `--compress`, `--compress-only`, `--compress-threshold`
- Compression step between candidate detection and archive/delete
- Uses haiku agent for summarization

**Advantages**:
- Natural part of maintenance workflow
- Reuses existing candidate detection
- Single command for all maintenance
- Optional via flags

**Disadvantages**:
- More complex gc command
- Gc becomes multi-purpose

**Risk Assessment**:
- **Complexity Risk**: Low. Additive feature.
- **Integration Risk**: Low. Natural extension.

### Option 3: Automatic Compression on Age

**Description**: Automatically compress memories when they reach a certain age.

**Technical Characteristics**:
- Hook-based automatic compression
- No user intervention needed
- Age-based triggers

**Advantages**:
- Fully automatic
- No user action required
- Consistent compression

**Disadvantages**:
- No user control
- May compress when not wanted
- Hook complexity

**Risk Assessment**:
- **Control Risk**: High. Users lose control.
- **Surprise Risk**: High. Unexpected changes.

## Decision

We will extend the `/mnemonic:gc` command with compression flags and use a haiku-based agent for summarization.

### New GC Flags

```bash
# Compress candidates after finding them
/mnemonic:gc --compress

# Only compress, don't archive/delete
/mnemonic:gc --compress-only

# Custom compression threshold (lines)
/mnemonic:gc --compress-threshold 100
```

### Compression Criteria

A memory is a compression candidate if:
- (Age > 30 days AND lines > 100) OR
- (strength < 0.3 AND lines > 100)

### Compression Agent

Create `agents/compression-worker.md`:
- Model: haiku (cost-effective)
- Input: Full memory content
- Output: JSON with summary, keywords, compressed_at
- Summary limit: 500 characters

### Storage Format

Add to frontmatter after provenance:

```yaml
summary: "Concise 2-3 sentence summary (max 500 chars)"
compressed_at: 2026-01-24T10:00:00Z
```

## Consequences

### Positive

1. **Integrated**: Natural part of maintenance workflow
2. **Optional**: Enabled only when requested
3. **Traceable**: Compression timestamp in frontmatter
4. **Cost-Effective**: Haiku model is cheap
5. **Reversible**: Original content preserved, summary added

### Negative

1. **GC Complexity**: Command has more options
2. **Agent Dependency**: Requires Task tool for compression

### Neutral

1. **Format Extension**: New summary field in MIF

## Decision Outcome

Extending gc with compression achieves:
- Integrated maintenance workflow
- User-controlled via flags
- Cost-effective with haiku
- Trackable via frontmatter

## Related Decisions

- [ADR-002: MIF Level 3 Format](adr-002-mif-level-3-format.md) - Format extended with summary field

## Links

- [Exponential Decay Model](https://en.wikipedia.org/wiki/Exponential_decay)

## More Information

- **Date:** 2026-01-24
- **Source:** Memory compression requirements

## Audit

### 2026-01-24

**Status:** Pending implementation

**Findings:** N/A - New ADR

**Action Required:** Implement compression-worker agent and gc extension

### 2026-10-08

**Status:** Amended for MIF 1.4.1

**Findings:** MIF 1.4.1 (section 5.6) names the compression timestamp
`compressedAt`. New compressions write `compressedAt`; the
`compressed_at` key shown under *Storage Format* is the pre-1.4.1 spelling
and is still read.

**Action Required:** None.
