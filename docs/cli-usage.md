# CLI Usage Guide

Command-line operations for mnemonic memories.

## Overview

Mnemonic memories are plain Markdown files with YAML frontmatter stored in predictable filesystem locations. This makes them fully accessible with standard CLI tools like `rg` (ripgrep), `find`, `grep`, `cat`, and `git`.

## Memory Locations

```bash
# User-level memories (cross-project)
${MNEMONIC_ROOT}/{org}/{namespace}/{scope}/*.memory.md

# Project-level memories
${MNEMONIC_ROOT}/{namespace}/{scope}/*.memory.md
```

**Namespaces:** apis, blockers, context, decisions, learnings, patterns, security, testing, episodic

**Scopes:** user, project

## Searching Memories

Mnemonic provides multiple search methods optimized for different use cases.

### Method 1: Semantic Vector Search (qmd)

For natural language queries and semantic understanding:

```bash
# One-time setup
/mnemonic:qmd-setup

# BM25 keyword ranking
qmd search "authentication middleware"

# Vector semantic search
qmd vsearch "how do we manage user permissions"

# Hybrid search (combines both)
qmd query "error handling best practices"

# Scope to specific collections
qmd search "api design" -c mnemonic-zircote     # org memories
qmd search "api design" -c mnemonic-project     # project memories
qmd search "api design"                         # all collections

# Limit results
qmd search "docker" -n 5

# Re-index after adding memories
/mnemonic:qmd-reindex
# or manually:
qmd update && qmd embed
```

**When to use:**
- Natural language queries
- Conceptual/semantic similarity
- Finding related memories across namespaces
- "What do we know about X" questions

**Requirements:**
- Node.js >= 22
- `npm i -g @tobilu/qmd`
- Initial setup with `/mnemonic:qmd-setup`

### Method 2: Full-Text Search with ripgrep

```bash
# Search all memories for a keyword
rg "postgresql" $MNEMONIC_ROOT --glob "*.memory.md"

# Case-insensitive search
rg -i "authentication" $MNEMONIC_ROOT --glob "*.memory.md"

# Search with context (3 lines before/after)
rg -C3 "api endpoint" $MNEMONIC_ROOT --glob "*.memory.md"

# List files only (no content)
rg -l "database" $MNEMONIC_ROOT --glob "*.memory.md"

# Search in specific namespace
rg "pattern" $MNEMONIC_ROOT/*/_semantic/decisions --glob "*.memory.md"

# Search project-level only
rg "bug fix" $MNEMONIC_ROOT --glob "*.memory.md"
```

### Search by Frontmatter Fields

```bash
# Find all semantic memories
rg "^type: semantic" $MNEMONIC_ROOT --glob "*.memory.md" -l

# Find memories with specific tag
rg "^  - architecture" $MNEMONIC_ROOT --glob "*.memory.md" -l

# Find memories from a date range
rg "^created: 2026-01" $MNEMONIC_ROOT --glob "*.memory.md" -l

# Find high-confidence memories
rg "confidence: 0.9" $MNEMONIC_ROOT --glob "*.memory.md" -l

# Find memories by title
rg "^title:.*PostgreSQL" $MNEMONIC_ROOT --glob "*.memory.md" -l
```

**When to use:**
- Exact phrase matching
- Known keywords
- Regular expressions
- Precise control over matching

### Method 3: Using find for File Operations

```bash
# List all memories
find ${MNEMONIC_ROOT} -name "*.memory.md"

# Find memories modified in last 7 days
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime -7

# Find memories older than 90 days
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime +90

# Count memories by namespace
find ${MNEMONIC_ROOT} -name "*.memory.md" | grep -o '/[^/]*/project\|/[^/]*/user' | sort | uniq -c
```

**When to use:**
- Time-based filtering
- File system operations
- Batch processing
- Directory traversal

### Search Method Comparison

| Feature | qmd (Semantic) | ripgrep | find |
|---------|---------------|---------|------|
| Natural language | ✅ Best | ❌ No | ❌ No |
| Exact matching | ⚠️ Good | ✅ Best | ❌ No |
| Speed | ⚠️ Moderate | ✅ Fast | ✅ Fast |
| Ranking | ✅ Relevance | ❌ No | ❌ No |
| Setup required | ⚠️ Yes | ✅ None | ✅ None |
| Regex support | ❌ No | ✅ Yes | ⚠️ Limited |
| Time filtering | ❌ No | ❌ No | ✅ Yes |

**Recommendation:**
- **Complex questions**: Use `qmd query`
- **Known keywords**: Use `rg`
- **Time-based**: Use `find` + `rg`

## Reading Memories

### View a Memory

```bash
# Read full memory
cat ${MNEMONIC_ROOT}/zircote/_semantic/decisions/550e8400-*.memory.md

# View just the title
grep "^title:" ${MNEMONIC_ROOT}/zircote/_semantic/decisions/*.memory.md

# View frontmatter only (between --- markers)
sed -n '/^---$/,/^---$/p' path/to/memory.memory.md

# View content only (after frontmatter)
sed '1,/^---$/d;/^---$/,$!d;/^---$/d' path/to/memory.memory.md
```

### Extract Specific Fields

```bash
# Get all memory IDs
grep "^id:" ${MNEMONIC_ROOT}/**/*.memory.md | cut -d: -f3 | tr -d ' '

# Get all unique tags
rg "^  - " $MNEMONIC_ROOT --glob "*.memory.md" -o | sort -u

# List all titles
grep "^title:" ${MNEMONIC_ROOT}/**/*.memory.md | sed 's/.*title: "//' | sed 's/"$//'
```

## Creating Memories

### Using a Template

```bash
# Generate UUID
UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# Generate timestamp
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Create memory file
cat > ${MNEMONIC_ROOT}/myorg/_semantic/decisions/${UUID}-my-decision.memory.md << EOF
---
id: ${UUID}
type: semantic
namespace: decisions/project
created: ${DATE}
modified: ${DATE}
title: "My Decision Title"
tags:
  - architecture
  - database
temporal:
  validFrom: ${DATE}
  recordedAt: ${DATE}
provenance:
  sourceType: user_explicit
  agent: cli
  confidence: 0.9
---

# My Decision Title

Description of the decision.

## Rationale

Why this decision was made.
EOF
```

### Quick Capture Script

Save as `~/bin/mnemonic-capture`:

```bash
#!/bin/bash
set -e

NAMESPACE="${1:?Usage: mnemonic-capture <namespace> <title>}"
TITLE="${2:?Usage: mnemonic-capture <namespace> <title>}"

ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' || echo "default")
UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 50)

MEMORY_DIR="$MNEMONIC_ROOT/$ORG/$NAMESPACE/user"
mkdir -p "$MEMORY_DIR"
MEMORY_FILE="$MEMORY_DIR/${SLUG}.memory.md"

cat > "$MEMORY_FILE" << EOF
---
id: ${UUID}
type: semantic
namespace: ${NAMESPACE}/user
created: ${DATE}
modified: ${DATE}
title: "${TITLE}"
tags:
  - manual
temporal:
  validFrom: ${DATE}
  recordedAt: ${DATE}
provenance:
  sourceType: user_explicit
  agent: cli
  confidence: 0.9
---

# ${TITLE}

EOF

# Open in editor
${EDITOR:-vim} "$MEMORY_FILE"

echo "Created: $MEMORY_FILE"
```

Usage:
```bash
chmod +x ~/bin/mnemonic-capture
mnemonic-capture decisions "Use Redis for caching"
```

## Managing Memories

### Git Operations

```bash
# View memory history
cd ${MNEMONIC_ROOT} && git log --oneline

# View changes to a specific memory
git log -p -- path/to/memory.memory.md

# Blame a memory (who wrote what)
git blame path/to/memory.memory.md

# Revert a memory to previous version
git checkout HEAD~1 -- path/to/memory.memory.md

# Commit changes
git add -A && git commit -m "Update: memory description"
```

### Backup and Sync

```bash
# Backup all memories
tar -czf mnemonic-backup-$(date +%Y%m%d).tar.gz ${MNEMONIC_ROOT}

# Sync to remote (after setting up remote)
cd ${MNEMONIC_ROOT}
git remote add origin git@github.com:user/mnemonic-memories.git
git push -u origin main

# Clone on new machine
git clone git@github.com:user/mnemonic-memories.git ${MNEMONIC_ROOT}
```

### Cleanup Operations

```bash
# Find memories older than 1 year
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime +365

# Find empty or small memories (< 100 bytes)
find ${MNEMONIC_ROOT} -name "*.memory.md" -size -100c

# Count memories by type
rg "^type:" $MNEMONIC_ROOT --glob "*.memory.md" -o | cut -d: -f2 | sort | uniq -c

# Find duplicate titles
grep "^title:" ${MNEMONIC_ROOT}/**/*.memory.md | cut -d: -f3- | sort | uniq -d
```

## Validation

### Validate Memory Format

```bash
# Check for required fields
validate_memory() {
    local file="$1"
    local errors=0

    grep -q "^id:" "$file" || { echo "Missing: id"; errors=1; }
    grep -q "^type:" "$file" || { echo "Missing: type"; errors=1; }
    grep -q "^namespace:" "$file" || { echo "Missing: namespace"; errors=1; }
    grep -q "^created:" "$file" || { echo "Missing: created"; errors=1; }
    grep -q "^title:" "$file" || { echo "Missing: title"; errors=1; }

    return $errors
}

# Validate all memories
for f in ${MNEMONIC_ROOT}/**/*.memory.md; do
    echo "Checking: $f"
    validate_memory "$f" || echo "  INVALID"
done
```

### Use the Validation Tool

```bash
# Validate all memories (from mnemonic repo)
python tools/mnemonic-validate ${MNEMONIC_ROOT}

# Validate with JSON output
python tools/mnemonic-validate --format json ${MNEMONIC_ROOT}

# Validate only changed files
python tools/mnemonic-validate --changed ${MNEMONIC_ROOT}
```

## Useful Aliases

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Quick search
alias ms='rg -i --glob "*.memory.md" ${MNEMONIC_ROOT}'

# List recent memories
alias mrecent='find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime -7 -exec grep -l "." {} \;'

# Count memories
alias mcount='find ${MNEMONIC_ROOT} -name "*.memory.md" | wc -l'

# Open memory directory
alias mdir='cd ${MNEMONIC_ROOT} && ls'

# Search by namespace
mns() {
    rg -i "$1" ${MNEMONIC_ROOT}/*/"$2" --glob "*.memory.md"
}
# Usage: mns "pattern" decisions
```

## Integration with Other Tools

### Structured Queries with yq

For structured frontmatter queries, use the `mnemonic-query` tool which leverages `yq` for proper YAML parsing:

```bash
# Install yq (required)
brew install yq       # macOS
apt install yq        # Ubuntu/Debian
pip install yq        # Python

# Basic queries
mnemonic-query --type semantic
mnemonic-query --tag architecture
mnemonic-query --namespace "decisions/*"

# Comparison operators
mnemonic-query --confidence ">0.8"
mnemonic-query --confidence ">=0.9"
mnemonic-query --confidence "<0.5"

# Range queries
mnemonic-query --confidence "0.7..0.9"
mnemonic-query --created "2026-01-01..2026-01-31"

# Inequality
mnemonic-query --type "!=episodic"

# Combine filters (AND)
mnemonic-query --type semantic --tag architecture --confidence ">0.8"

# Pipe to content search
mnemonic-query --tag security | xargs rg "password"
```

#### Query Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `=` (implicit) | `--confidence 0.9` | Exact match |
| `!=` | `--type "!=episodic"` | Not equal |
| `>` | `--confidence ">0.8"` | Greater than |
| `>=` | `--confidence ">=0.9"` | Greater or equal |
| `<` | `--confidence "<0.5"` | Less than |
| `<=` | `--confidence "<=0.7"` | Less or equal |
| `..` | `--confidence "0.7..0.9"` | Range (inclusive) |

#### Output Formats

```bash
# File paths (default)
mnemonic-query --type semantic

# Titles only
mnemonic-query --type semantic --format titles

# JSON with full metadata
mnemonic-query --type semantic --format json

# Count only
mnemonic-query --type semantic --format count

# Limit results
mnemonic-query --type semantic --limit 10
```

### Raw yq for Manual YAML Parsing

```bash
# Extract frontmatter as JSON
sed -n '/^---$/,/^---$/p' memory.memory.md | yq -o=json

# Query specific fields
sed -n '/^---$/,/^---$/p' memory.memory.md | yq '.tags[]'

# Extract confidence value
sed -n '/^---$/,/^---$/p' memory.memory.md | yq '.provenance.confidence'

# Check if tag exists
sed -n '/^---$/,/^---$/p' memory.memory.md | yq '.tags | contains(["security"])'
```

### Generate Reports

```bash
# Memory summary report
echo "# Memory Report - $(date +%Y-%m-%d)"
echo ""
echo "## Counts by Namespace"
find ${MNEMONIC_ROOT} -name "*.memory.md" | \
    sed 's|.*/\([^/]*\)/[^/]*/[^/]*$|\1|' | sort | uniq -c | sort -rn

echo ""
echo "## Recent Activity (7 days)"
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime -7 -exec grep "^title:" {} \;
```

### Watch for Changes

```bash
# Monitor memory directory for changes (requires fswatch)
fswatch -o ${MNEMONIC_ROOT} | while read; do
    echo "Memory change detected at $(date)"
done
```

## Troubleshooting

### Common Issues

**"No memories found"**
```bash
# Check if directory exists
ls -la ${MNEMONIC_ROOT}

# Check organization detection
git remote get-url origin | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|'
```

**"ripgrep not found"**
```bash
# Install ripgrep
brew install ripgrep    # macOS
apt install ripgrep     # Ubuntu/Debian
```

**"Git not initialized"**
```bash
cd ${MNEMONIC_ROOT}
git init
git add .
git commit -m "Initialize mnemonic"
```

## See Also

- [Architecture](architecture.md) - System design overview
- [Validation](validation.md) - MIF schema validation
- [Agent Coordination](agent-coordination.md) - Multi-agent patterns
