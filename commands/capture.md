---
name: capture
allowed-tools:
- Bash
- Write
- Read
- Glob
- Grep
argument-hint: <namespace> <title> [--type semantic|episodic|procedural] [--tags tag1,tag2]
  [--scope project|org] [--citations JSON]
description: Capture a new memory
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# /mnemonic:capture

Capture a new memory to the mnemonic filesystem.

## Arguments

- `<namespace>` - Required. Hierarchical namespace path using cognitive triad (prefixed with _ for filesystem disambiguation):
  - **Semantic** (facts/knowledge): `_semantic/decisions`, `_semantic/knowledge`, `_semantic/entities`
  - **Episodic** (events/experiences): `_episodic/incidents`, `_episodic/sessions`, `_episodic/blockers`
  - **Procedural** (processes/steps): `_procedural/runbooks`, `_procedural/patterns`, `_procedural/migrations`
- `<title>` - Required. Human-readable title for the memory
- `--type` - Memory type: semantic (default), episodic, or procedural
- `--tags` - Comma-separated list of tags
- `--scope` - project (default, current project) or org (shared across all projects in organization)
- `--confidence` - Confidence score 0.0-1.0 (default: 0.95)
- `--citations` - JSON array of citation objects (see format skill for schema)
- `--entity-type` - Entity type from ontology (e.g., technology, component, runbook)
- `--entity-id` - Custom entity ID (auto-generated if not provided)

## Procedure

### Step 1: Parse Arguments

```bash
NAMESPACE="${1:-decisions}"
TITLE="${2:-Untitled Memory}"
TYPE="${TYPE:-semantic}"
SCOPE="${SCOPE:-project}"
CONFIDENCE="${CONFIDENCE:-0.95}"
TAGS="${TAGS:-}"
```

### Step 2: Validate Namespace

```bash
# Use ontology registry to validate namespace (includes base + user + project ontologies)
PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-$(dirname $(dirname $0))}"
if python3 "$PLUGIN_DIR/skills/ontology/lib/ontology_registry.py" --validate "$NAMESPACE" >/dev/null 2>&1; then
    echo "Namespace '$NAMESPACE' validated"
else
    echo "Error: Invalid namespace '$NAMESPACE'"
    echo "Valid namespaces:"
    python3 "$PLUGIN_DIR/skills/ontology/lib/ontology_registry.py" --namespaces
    exit 1
fi
```

### Step 2a: Validate Against Ontology

Before creating the memory, validate the namespace and type against the loaded ontology:

```python
# Python validation (called programmatically or mentally verified)
from lib.ontology import validate_memory_against_ontology, load_ontology_data

ontology = load_ontology_data()
errors = validate_memory_against_ontology(NAMESPACE, TYPE, ontology)
if errors:
    for err in errors:
        print(f"Validation error: {err}")
    # Show valid namespaces and abort
    exit(1)
```

If the namespace is not recognized by any loaded ontology, report a clear error with the list of valid namespaces and do NOT proceed with capture.

### Step 2b: Dedup Check (MANDATORY)

**Before creating any memory, check for duplicates:**

1. Search for existing memories with similar keywords:
   ```bash
   rg -i "{key_words_from_title}" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l | head -5
   ```

2. If matches found, read the top result
3. If it covers the same topic → UPDATE existing memory (use Edit tool) instead of creating new
4. If related but different → create new memory with a `relates-to` relationship
5. Only create brand new if no matches found

### Step 3: Generate Identifiers

**CRITICAL: You MUST execute these commands to generate real values. NEVER write placeholder text like "PLACEHOLDER_UUID" or "PLACEHOLDER_DATE" into memory files.**

```bash
# UUID - MUST be a real UUID, not a placeholder
UUID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')
[ -z "$UUID" ] && UUID=$(python3 -c "import uuid; print(uuid.uuid4())")

# Slug from title
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 50)

# Timestamp - MUST be a real ISO 8601 timestamp, not a placeholder
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Organization
ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' | sed 's|\.git$||')
[ -z "$ORG" ] && ORG="default"
```

**Validation:** Before proceeding, verify UUID looks like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` and DATE looks like `2026-01-28T12:00:00Z`. If either is empty or a placeholder, re-run the generation commands.

### Step 3b: Validate Type Matches Namespace

```bash
# Infer expected type from namespace path
case "$NAMESPACE" in
    _semantic/*) EXPECTED_TYPE="semantic" ;;
    _procedural/*) EXPECTED_TYPE="procedural" ;;
    _episodic/*) EXPECTED_TYPE="episodic" ;;
    *) EXPECTED_TYPE="$TYPE" ;;
esac

if [ "$TYPE" != "$EXPECTED_TYPE" ]; then
    echo "Warning: type '$TYPE' does not match namespace '$NAMESPACE' (expected '$EXPECTED_TYPE'). Correcting."
    TYPE="$EXPECTED_TYPE"
fi
```

### Step 4: Determine Path

```bash
# Resolve MNEMONIC_ROOT from config
if [ -f "$HOME/.config/mnemonic/config.json" ]; then
    RAW_PATH=$(python3 -c "import json; print(json.load(open('$HOME/.config/mnemonic/config.json')).get('memory_store_path', '~/.claude/mnemonic'))")
    MNEMONIC_ROOT="${RAW_PATH/#\~/$HOME}"
else
    MNEMONIC_ROOT="$HOME/.claude/mnemonic"
fi

# Get project name from git remote or directory
PROJECT=$(git remote get-url origin 2>/dev/null | sed -E 's|.*/([^/]+)\.git$|\1|' | sed 's|\.git$||')
[ -z "$PROJECT" ] && PROJECT=$(basename "$(pwd)")

# All memories are stored under ${MNEMONIC_ROOT}/
# Path structure: {org}/{project}/{namespace}/ for project scope
#                 {org}/{namespace}/ for org scope (when --scope org)
if [ "$SCOPE" = "org" ]; then
    # Org-wide memory (shared across projects in org)
    MEMORY_DIR="${MNEMONIC_ROOT}/${ORG}/${NAMESPACE}"
else
    # Project-specific memory (default)
    MEMORY_DIR="${MNEMONIC_ROOT}/${ORG}/${PROJECT}/${NAMESPACE}"
fi

mkdir -p "$MEMORY_DIR"
MEMORY_FILE="${MEMORY_DIR}/${SLUG}.memory.md"
```

**If `$MEMORY_FILE` already exists:** This memory will be merged with the existing file. Read the existing content, combine it with the new content under a `## Merged Content` separator, and keep the existing file's `id:` and `created:` fields. Update the `modified:` timestamp to now.

### Step 5: Format Tags

```bash
# Convert comma-separated to YAML list
if [ -n "$TAGS" ]; then
    TAGS_YAML=$(echo "$TAGS" | tr ',' '\n' | sed 's/^/  - /' | sed 's/^ *- */  - /')
else
    TAGS_YAML="  - untagged"
fi
```

### Step 5b: Format Citations (Optional)

If `--citations` is provided as a JSON array, convert to YAML:

```bash
# CITATIONS is optional JSON array: '[{"type":"paper","title":"...","url":"..."}]'
if [ -n "$CITATIONS" ]; then
    # Parse JSON and format as YAML (Claude will handle this conversion)
    CITATIONS_YAML="citations:"
    # Each citation becomes:
    #   - type: paper
    #     title: "..."
    #     url: https://...
    #     accessed: 2026-01-24T10:00:00Z
else
    CITATIONS_YAML=""
fi
```

**Citation fields:**
- `type` (required): paper, documentation, blog, github, stackoverflow, article
- `title` (required): Human-readable title
- `url` (required): Full URL
- `author` (optional): Author name
- `date` (optional): Publication date
- `accessed` (optional): When accessed
- `relevance` (optional): 0.0-1.0
- `note` (optional): Brief description

### Step 6: Prompt for Content

Ask the user to provide the memory content. This should include:
- Main description
- Rationale or context
- Any code references
- Related memories

### Step 7: Create Memory File

**CRITICAL: Replace ALL variables below with the REAL values generated in Steps 1-5. Every `{VARIABLE}` must be substituted. No placeholders may appear in the final file.**

Use the Write tool to create the file at `$MEMORY_FILE` with this structure (all variables substituted with real values):

```yaml
---
id: <real UUID from Step 3>
type: <real TYPE from Step 1>
namespace: <real NAMESPACE from Step 1>
created: <real DATE from Step 3>
modified: <real DATE from Step 3>
title: "<real TITLE from Step 1>"
tags:
<real TAGS_YAML from Step 5>
temporal:
  validFrom: <real DATE from Step 3>
  recordedAt: <real DATE from Step 3>
  lastAccessed: <real DATE from Step 3>
  decay:
    model: exponential
    halfLife: P90D
    strength: 1.0
provenance:
  sourceType: agent_inferred   # user_explicit if the user stated it directly
  agent: claude-opus-4
  confidence: <real CONFIDENCE from Step 1>
---

# <real TITLE>

<real CONTENT from Step 6>

## Rationale

<real RATIONALE from Step 6>
```

**Validation (MANDATORY — do NOT skip):** After writing, read the first 10 lines of the file and verify:
1. `id:` contains a real UUID matching `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` (not "PLACEHOLDER", "${UUID}", or any template variable)
2. `created:` contains a real ISO 8601 timestamp (not "PLACEHOLDER", "${DATE}", or any template variable)
3. `type:` matches the namespace path (`_semantic/` → semantic, `_procedural/` → procedural, `_episodic/` → episodic)

If ANY check fails, delete the file and re-run from Step 3.

### Step 7b: Add Ontology Fields (if --entity-type provided)

If `--entity-type` is specified, add ontology metadata:

```yaml
# ONTOLOGY_YAML (if entity-type provided):
ontology:
  entity_type: {ENTITY_TYPE}
  entity_id: {ENTITY_ID}

# ENTITY_YAML (entity-specific fields based on schema):
entity:
  name: "{extracted from title}"
  # Additional fields based on entity type schema
```

When capturing with an entity type:
1. Look up entity type schema from loaded ontology
2. Prompt user for required fields
3. Include entity block in frontmatter
4. Claude suggests entity references in content using `@[[Name]]` syntax

### Step 8: Commit to Git

```bash
cd ${MNEMONIC_ROOT}
git add -A
git commit -m "Capture: ${TITLE}"
cd -
```

### Step 9: Report

```bash
echo "Memory captured:"
echo "  ID: $UUID"
echo "  File: $MEMORY_FILE"
echo "  Namespace: $NAMESPACE/$SCOPE"
echo "  Type: $TYPE"
```

## Example Usage

```
/mnemonic:capture _semantic/decisions "Use PostgreSQL for data storage" --tags database,architecture
/mnemonic:capture _procedural/patterns "Repository pattern for data access" --tags database,patterns
/mnemonic:capture _episodic/incidents "Database connection timeout issue" --type episodic
```

### Example with Citations

```
/mnemonic:capture _semantic/knowledge "PostgreSQL JSON Performance" --tags database,performance --citations '[{"type":"paper","title":"PostgreSQL vs MySQL Performance","url":"https://arxiv.org/abs/2024.12345","author":"Smith et al.","relevance":0.95}]'
```

## Output

Display:
- Generated UUID
- File path
- Namespace and scope
- Memory type
- Confirmation of git commit
