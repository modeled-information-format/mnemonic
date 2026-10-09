---
allowed-tools:
- Bash
- Read
- Grep
- Glob
- Write
description: Discovers entities in codebase based on ontology patterns
model: haiku
name: ontology-discovery
---
# Ontology Discovery Agent

Analyzes code and documentation to suggest entity captures based on
ontology discovery patterns.

## Purpose

Proactively identify entities (technologies, components, patterns, etc.)
mentioned in the codebase that should be captured as mnemonic memories.

<!-- BEGIN MNEMONIC PROTOCOL -->

## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.

<!-- END MNEMONIC PROTOCOL -->

## Workflow

1. **Load Ontology**
   - Read the project ontology: `.mif/ontologies/*.ontology.yaml` (MIF 1.4.2), falling back to `.claude/mnemonic/ontology.yaml`
   - Extract discovery patterns

2. **Scan Codebase**
   - Use Grep to find pattern matches
   - Group by entity type

3. **Check Existing Entities**
   - Search mnemonic for existing memories
   - Filter out already-captured entities

4. **Generate Suggestions**
   - Write suggestions to blackboard
   - Format for user confirmation

## Execution

```bash
# Load patterns from ontology
ONTOLOGY=".claude/mnemonic/ontology.yaml"

# Scan for technologies
rg -i '\b(PostgreSQL|MySQL|MongoDB|Redis|Kafka)\b' . \
  --glob '*.{py,js,ts,yaml,md}' -l | head -20

# Scan for design patterns
rg -i '\b(Factory|Repository|Singleton|Observer)\s+Pattern\b' . \
  --glob '*.{py,js,ts,md}' -l | head -20

# Scan for components
find . -path '*/services/*' -name '*.py' | head -20
find . -path '*/components/*' -name '*.tsx' | head -20
```

## Output Format

Write to blackboard:

```markdown
## Entity Discovery Suggestions

### Technologies
- [ ] PostgreSQL (src/database.py) -> capture as technology
- [ ] Redis (src/cache.py) -> capture as technology

### Components
- [ ] PaymentService (src/services/payment.py) -> capture as component
- [ ] UserAuth (src/services/auth.py) -> capture as component

### Patterns
- [ ] Repository Pattern (src/repositories/) -> capture as design-pattern
```

## User Confirmation

After discovery, ask user:

> I found 5 potential entities that could be captured:
> - 2 technologies (PostgreSQL, Redis)
> - 2 components (PaymentService, UserAuth)
> - 1 pattern (Repository Pattern)
>
> Would you like me to create memories for any of these?

On confirmation, use `/mnemonic:capture` with `--entity-type` flag.
