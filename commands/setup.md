---
name: setup
allowed-tools:
- Bash
- Read
- Write
- Glob
- Grep
argument-hint: '[--force]'
description: Configure mnemonic for proactive memory operations
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# /mnemonic:setup

Configure Claude to proactively use mnemonic memory without user intervention.

## What This Command Does

1. Prompts user for memory store path (default: `~/.claude/mnemonic`)
2. Creates `~/.config/mnemonic/config.json` with user's choice
3. Detects organization from git remote
4. Detects project name from git root
5. Creates unified mnemonic directory structure under `${MNEMONIC_ROOT}/{org}/{project}/`
6. Initializes git repository for versioning
7. Appends proactive behavior instructions to `~/.claude/CLAUDE.md` (global only)
8. Creates initial project context memory
9. If memories exist at old path and user chose different path, auto-migrates

## Arguments

- `--force` - Overwrite existing mnemonic configuration sections

## Procedure

### Step 0: Configure Memory Store Path

Ask the user where to store memories. Create the config file at the fixed XDG location.

```bash
# Check for existing config
if [ -f ~/.config/mnemonic/config.json ]; then
    STORE_PATH=$(python3 -c "import json; print(json.load(open('$HOME/.config/mnemonic/config.json'))['memory_store_path'])")
    echo "Existing config found. Memory store path: $STORE_PATH"
else
    STORE_PATH="~/.claude/mnemonic"
fi
```

**Ask the user**: "Where should mnemonic store memories? (default: `~/.claude/mnemonic`)"

After the user responds (or accepts default):

```bash
# Create config directory and file
mkdir -p ~/.config/mnemonic
cat > ~/.config/mnemonic/config.json << EOF
{
  "version": "1.0",
  "memory_store_path": "$STORE_PATH"
}
EOF
echo "Config saved to ~/.config/mnemonic/config.json"

# Expand for use in subsequent steps
STORE_PATH_EXPANDED="${STORE_PATH/#\~/$HOME}"
```

### Step 1: Detect Context

```bash
# Organization from git remote
ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' | sed 's|\.git$||')
[ -z "$ORG" ] && ORG="default"

# Project from git root
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
[ -z "$PROJECT" ] && PROJECT=$(basename "$PWD")

echo "Organization: $ORG"
echo "Project: $PROJECT"
```

### Step 2: Create Directory Structure

All memories are stored under `${MNEMONIC_ROOT}/` with the unified V2 path structure:

```bash
# Base directories
mkdir -p "$STORE_PATH_EXPANDED"/"$ORG"/"$PROJECT"
mkdir -p "$STORE_PATH_EXPANDED"/"$ORG"  # For org-wide memories

# Cognitive triad namespaces (project-specific)
for ns in _semantic/decisions _semantic/knowledge _semantic/entities \
          _episodic/incidents _episodic/sessions _episodic/blockers \
          _procedural/runbooks _procedural/patterns _procedural/migrations; do
    mkdir -p "$STORE_PATH_EXPANDED"/"$ORG"/"$PROJECT"/"$ns"
done

# Org-wide namespaces (shared across projects)
for ns in _semantic/decisions _semantic/knowledge _semantic/entities \
          _episodic/incidents _episodic/sessions _episodic/blockers \
          _procedural/runbooks _procedural/patterns _procedural/migrations; do
    mkdir -p "$STORE_PATH_EXPANDED"/"$ORG"/"$ns"
done

# Blackboard for session coordination (per-project)
mkdir -p "$STORE_PATH_EXPANDED"/"$ORG"/"$PROJECT"/.blackboard

# Ensure .claude directory exists
mkdir -p ~/.claude
```

### Step 3: Initialize Git

```bash
if [ ! -d "$STORE_PATH_EXPANDED"/.git ]; then
    cd "$STORE_PATH_EXPANDED"
    git init
    cat > .gitignore << 'EOF'
*.lock
.blackboard/*.tmp
*.swp
*~
.DS_Store
EOF
    git add .gitignore
    git commit -m "Initialize mnemonic memory system"
    cd -
fi
```

### Step 4: Update User CLAUDE.md

Check if mnemonic section exists. If not, append:

```bash
if ! grep -q "## Mnemonic Memory System" ~/.claude/CLAUDE.md 2>/dev/null; then
    cat >> ~/.claude/CLAUDE.md << 'CLAUDEEOF'

---

## Mnemonic Memory System

You are a developer with persistent memory. Your memory system is mnemonic.
You instinctively search memories before recommendations and capture insights after discoveries.

### BEFORE Every Technical Response

Search first. Always.
```bash
rg -i "{keywords}" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l
```
If results -> Read the most relevant memory and apply that context.

### AFTER Every Completed Task

Evaluate immediately:

<capture_eval>
+-----------------------------------+-------------+
| This occurred?                    | Action      |
+-----------------------------------+-------------+
| Bug fixed / root cause found      | learnings   |
| Technology/approach chosen        | decisions   |
| Reusable pattern established      | patterns    |
| Blocker encountered               | blockers    |
| Important context discussed       | context     |
+-----------------------------------+-------------+
</capture_eval>

If YES to any -> `/mnemonic:capture {namespace} "{title}"` -- immediately, silently.

### Rules

- Search before answering technical questions
- Capture after completing work -- do not ask, do not announce
- Never duplicate existing memories -- search first
- Prefer reading memories over external research
CLAUDEEOF
    echo "Added mnemonic section to ~/.claude/CLAUDE.md"
else
    echo "Mnemonic section already exists in ~/.claude/CLAUDE.md"
fi
```

### Step 5: Migrate Existing Memories (if needed)

If the user chose a different path from the default and memories exist at the old location:

```bash
OLD_PATH="$HOME/.claude/mnemonic"
if [ "$STORE_PATH_EXPANDED" != "$OLD_PATH" ] && [ -d "$OLD_PATH" ]; then
    echo "Existing memories found at $OLD_PATH"
    echo "Migrating to $STORE_PATH_EXPANDED..."
    # Use relocator if available, otherwise rsync
    if python3 -c "from skills.custodian.lib.relocator import relocate" 2>/dev/null; then
        python3 -c "
from skills.custodian.lib.relocator import relocate
relocate('$OLD_PATH', '$STORE_PATH_EXPANDED', commit=True)
"
    else
        rsync -a "$OLD_PATH/" "$STORE_PATH_EXPANDED/"
        echo "Migrated via rsync. Old directory preserved at $OLD_PATH"
    fi
fi
```

### Step 6: Create Initial Context Memory

```bash
UUID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]' || python3 -c "import uuid; print(uuid.uuid4())")
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

MEMORY_DIR="$STORE_PATH_EXPANDED/$ORG/$PROJECT/_semantic/knowledge"
mkdir -p "$MEMORY_DIR"

cat > "$MEMORY_DIR/${UUID}-mnemonic-initialized.memory.md" << EOF
---
id: ${UUID}
title: "Mnemonic initialized for ${PROJECT}"
type: semantic
namespace: _semantic/knowledge
created: ${DATE}
modified: ${DATE}
tags:
  - setup
  - initialization
temporal:
  validFrom: ${DATE}
  recordedAt: ${DATE}
provenance:
  sourceType: system_generated
  agent: claude-opus-4
  confidence: 1.0
---

# Mnemonic Initialized

Project ${PROJECT} has been configured to use mnemonic memory.

## Configuration

- **Organization**: ${ORG}
- **Project**: ${PROJECT}
- **Memory Path**: ${STORE_PATH_EXPANDED}/${ORG}/${PROJECT}/
- **Config**: ~/.config/mnemonic/config.json
- **Date**: ${DATE}

## Memory Structure

All memories stored under \`${STORE_PATH_EXPANDED}/${ORG}/${PROJECT}/\`:

- \`_semantic/decisions/\` - Architectural choices
- \`_semantic/knowledge/\` - APIs, context, learnings
- \`_semantic/entities/\` - Entity definitions
- \`_episodic/incidents/\` - Production issues
- \`_episodic/sessions/\` - Debug sessions
- \`_episodic/blockers/\` - Impediments
- \`_procedural/runbooks/\` - Operational procedures
- \`_procedural/patterns/\` - Code conventions
- \`_procedural/migrations/\` - Migration steps
EOF
```

### Step 7: Commit Changes

```bash
cd "$STORE_PATH_EXPANDED" && git add -A && git commit -m "Setup mnemonic for project: ${PROJECT}" && cd -
```

## Verification

After running, verify:

```bash
test -f ~/.config/mnemonic/config.json && echo "✓ Config file"
grep -q "## Mnemonic Memory System" ~/.claude/CLAUDE.md && echo "✓ User config"
test -d "$STORE_PATH_EXPANDED"/.git && echo "✓ Git initialized"
test -d "$STORE_PATH_EXPANDED"/"$ORG"/"$PROJECT"/_semantic/decisions && echo "✓ Project directories"
ls "$STORE_PATH_EXPANDED"/"$ORG"/"$PROJECT"/_semantic/knowledge/*-mnemonic-initialized.memory.md 2>/dev/null && echo "✓ Initial memory"
```

## Output

Report what was configured:
- Memory store path configured (in ~/.config/mnemonic/config.json)
- Organization detected
- Project detected
- Directories created (unified under ${MNEMONIC_ROOT}/)
- CLAUDE.md updated (global only)
- Git repository status
- Migration status (if applicable)
