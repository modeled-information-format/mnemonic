---
applyTo: "**/*.memory.md"
---

# Memory File Guidelines (MIF 1.4.1 Level 3)

Concept frontmatter keys are camelCase (MIF 1.4.1 section 3.3). Legacy
snake_case keys (`valid_from`, `source_type`, `compressed_at`) in older
memories are still read; do not introduce them in new or edited files.

## Required Frontmatter Fields

```yaml
---
id: <uuid>                    # Unique identifier (uuidgen format)
type: semantic|episodic|procedural
namespace: {category}/user    # e.g., decisions/user, learnings/user
created: <ISO8601>            # Creation timestamp
modified: <ISO8601>           # Last modification timestamp
title: "Title"                # Human-readable title
tags: [tag1, tag2]            # Categorization tags
---
```

## Optional Temporal Fields

```yaml
temporal:
  validFrom: <ISO8601>       # When content became valid
  validUntil: <ISO8601>      # When content expires (optional)
  recordedAt: <ISO8601>      # When it was recorded
  decay:
    model: exponential        # Decay model type
    halfLife: P7D            # ISO 8601 duration
    strength: 0.85            # Current strength 0.0-1.0
```

## Optional Provenance Fields

```yaml
provenance:
  sourceType: user_explicit | user_implicit | agent_inferred | external_import | system_generated
  agent: model-identifier     # e.g., claude-opus-4
  confidence: 0.9             # Confidence score 0.0-1.0
```

## Memory Types

- **semantic**: Facts, decisions, specifications - things that ARE true
- **episodic**: Events, debug sessions, incidents - things that HAPPENED
- **procedural**: Workflows, patterns, how-tos - things you DO

## Content Structure

After frontmatter, use standard Markdown:
- H1 heading matching the title
- Clear sections for context, details, implications
- Code blocks with language specification
- Links to related memories or external resources

## Relationships

Relationships are authoritative in frontmatter and mirrored as Markdown links
under `## Relationships` (MIF 1.4.1 section 5.3):

```yaml
relationships:
  - type: relates-to                 # kebab-case token, not relates_to
    target: urn:mif:<target-uuid>
    metadata:
      label: "Optional note"
```

```markdown
## Relationships

- relates-to [Target Title](urn:mif:<target-uuid>)
```

Do not use `[[uuid]]` wiki-links for relationships.
