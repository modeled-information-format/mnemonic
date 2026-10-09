# Capture Workflow

Complete workflow for capturing memories to mnemonic.

## Step 1: Generate UUID

```bash
# macOS/Linux with uuidgen
UUID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')

# Fallback to Python
[ -z "$UUID" ] && UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
```

## Step 2: Determine Namespace and Scope

| Content Type | Namespace | Example |
|--------------|-----------|---------|
| API documentation | apis | REST endpoint specs |
| Problems/issues | blockers | Bug that blocked progress |
| Background info | context | Project setup, environment |
| Architectural choices | decisions | "We chose PostgreSQL because..." |
| Insights/discoveries | learnings | "TIL that X works better than Y" |
| Code conventions | patterns | "Always use factory pattern for..." |
| Security policies | security | "Never store secrets in..." |
| Test strategies | testing | "Edge case: empty input..." |
| Events/experiences | episodic | Debug session, incident |

**Scope Selection:**
- `user/` - Personal knowledge, cross-project
- `project/` - Specific to current codebase

## Step 2.5: Dedup Check (MANDATORY)

**Before creating any memory, check for duplicates:**

1. Search for existing memories with similar keywords:
   ```bash
   rg -i "{key_words}" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l | head -5
   ```

2. If matches found, read the top result
3. If it covers the same topic → UPDATE existing memory (use Edit tool) instead of creating new
4. If related but different → create new memory with a `relates-to` relationship
5. Only create brand new if no matches found

## Step 3: Classify Cognitive Type

| Type | When to Use | Indicators | Required Namespace Prefix |
|------|-------------|------------|--------------------------|
| `semantic` | Facts, concepts, specifications | "X is Y", definitions, docs | `_semantic/*` |
| `episodic` | Events, experiences, incidents | "When we...", timestamps | `_episodic/*` |
| `procedural` | Processes, workflows, how-tos | "To do X, first...", steps | `_procedural/*` |

**Type MUST match the namespace path.** A memory in `_procedural/patterns/` must have `type: procedural`.

## Step 3.5: Discover Related Memories

After determining the namespace and title, search for related memories to establish connections.

**Why relationships matter:**
- Link related decisions together
- Track knowledge evolution (supersedes, derived-from)
- Enable graph-based memory navigation
- Prevent duplicates by surfacing similar memories

**Search for related memories:**

```bash
# Search using title keywords and namespace
rg -i "{title_keywords}" ${MNEMONIC_ROOT} --glob "*.memory.md" -l | head -5
```

**Review candidates and determine relationship types:**

For each candidate memory, evaluate:

| Relationship Type | When to Use | Example |
|------------------|-------------|---------|
| `supersedes` | This memory replaces/updates an older one | New decision overrides previous approach |
| `derived-from` | This memory builds on another | Implementation pattern based on architecture decision |
| `relates-to` | Thematically connected | Two related but independent decisions |

**Decision criteria:**
- Same namespace + similar title keywords (>50% overlap) → `supersedes`
- Different namespace + shared concepts (>30% overlap) → `derived-from`
- Thematic connection without direct evolution → `relates-to`

**Include discovered relationships in frontmatter:**

If you find related memories, add them to the `relationships:` field in Step 4.

## Step 4: Create Memory File

**CRITICAL: Always generate REAL values. Never write placeholders like "PLACEHOLDER_UUID" or "PLACEHOLDER_DATE".**

**File naming:** `{slug}.memory.md`

**Optional fields:**
- `tags: [tag1, tag2]` - categorization tags
- `namespace: _semantic/decisions` - explicit namespace path
- `relationships:` - links to other memories (see Step 3.5)
  ```yaml
  relationships:
    - type: supersedes
      target: urn:mif:<target-uuid>
      metadata:
        label: "Replaces old approach"
    - type: relates-to
      target: urn:mif:<target-uuid>
      metadata:
        label: "Related decision"
  ```
  Mirror each one in the body under `## Relationships` as
  `- supersedes [Target Title](urn:mif:<target-uuid>)` (MIF 1.4.2 section 5.3).

```bash
# Resolve MNEMONIC_ROOT from config
if [ -f "$HOME/.config/mnemonic/config.json" ]; then
    RAW_PATH=$(python3 -c "import json; print(json.load(open('$HOME/.config/mnemonic/config.json')).get('memory_store_path', '~/.claude/mnemonic'))")
    MNEMONIC_ROOT="${RAW_PATH/#\~/$HOME}"
else
    MNEMONIC_ROOT="$HOME/.claude/mnemonic"
fi
# Generate real values - NEVER use placeholder text
UUID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')
[ -z "$UUID" ] && UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
NAMESPACE="decisions"
SCOPE="project"
TYPE="semantic"
TITLE="Use PostgreSQL for data storage"
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 50)
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Determine path
# Get org and project for proper namespace routing
ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' | sed 's|\.git$||')
[ -z "$ORG" ] && ORG="default"
PROJECT=$(git remote get-url origin 2>/dev/null | sed -E 's|.*/([^/]+)\.git$|\1|' | sed 's|\.git$||')
[ -z "$PROJECT" ] && PROJECT=$(basename "$(pwd)")

if [ "$SCOPE" = "project" ]; then
    # Project-specific: org/project/namespace/
    MEMORY_DIR="${MNEMONIC_ROOT}/${ORG}/${PROJECT}/${NAMESPACE}"
else
    # Org-wide: org/namespace/
    MEMORY_DIR="${MNEMONIC_ROOT}/${ORG}/${NAMESPACE}"
fi

mkdir -p "$MEMORY_DIR"

# Create memory file (minimal format)
cat > "${MEMORY_DIR}/${SLUG}.memory.md" << MEMORY_EOF
---
id: ${UUID}
title: "${TITLE}"
type: ${TYPE}
namespace: ${NAMESPACE}
created: ${DATE}
modified: ${DATE}
tags: []
temporal:
  validFrom: ${DATE}
  recordedAt: ${DATE}
  lastAccessed: ${DATE}
  decay:
    model: exponential
    halfLife: P90D
    strength: 1.0
provenance:
  sourceType: agent_inferred
  agent: "claude"
  confidence: 0.8
---

# ${TITLE}

## Summary

[One sentence summary]

## Details

[Full content here]
MEMORY_EOF
```

## Step 4b: Post-Write Validation (MANDATORY)

After writing the file, read the first 10 lines and verify:
1. `id:` contains a real UUID (`[0-9a-f]{8}-...-[0-9a-f]{12}`) — not a placeholder or template variable
2. `created:` contains a real ISO 8601 timestamp — not a placeholder
3. `type:` matches the namespace path (`_semantic/` → semantic, `_procedural/` → procedural, `_episodic/` → episodic)

If ANY check fails, delete the file and re-run from Step 1.

## Step 5: Git Commit

```bash
cd ${MNEMONIC_ROOT}
git add -A
git commit -m "Capture: ${TITLE}"
cd -
```
