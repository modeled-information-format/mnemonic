---
name: gc
allowed-tools:
- Bash
- Read
- Write
- Task
- Glob
- Grep
argument-hint: '[--dry-run] [--archive] [--force] [--compress]'
description: Garbage collect expired memories
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# /mnemonic:gc

Garbage collect expired memories based on TTL and decay, with optional compression.

## Arguments

- `--dry-run` - Show what would be removed without removing
- `--archive` - Move to archive instead of deleting
- `--force` - Skip confirmation prompts
- `--min-strength` - Minimum strength threshold (default: 0.1)
- `--max-age` - Maximum age in days (default: 365)
- `--compress` - Compress large old memories before archiving
- `--compress-only` - Only compress, don't archive/delete
- `--compress-threshold` - Minimum lines for compression (default: 100)

## Procedure

### Step 1: Parse Arguments

```bash
DRY_RUN="${DRY_RUN:-false}"
ARCHIVE="${ARCHIVE:-true}"
FORCE="${FORCE:-false}"
MIN_STRENGTH="${MIN_STRENGTH:-0.1}"
MAX_AGE="${MAX_AGE:-365}"

ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' | sed 's|\.git$||')
[ -z "$ORG" ] && ORG="default"

ARCHIVE_DIR="$HOME/.claude/mnemonic/.archive/$(date +%Y-%m)"
```

### Step 2: Find Candidates

#### By Age

```bash
echo "=== Finding GC Candidates ==="
echo ""

echo "Old memories (> $MAX_AGE days):"
OLD_FILES=$(find "$HOME/.claude/mnemonic/$ORG" "./.claude/mnemonic" -name "*.memory.md" -mtime +$MAX_AGE 2>/dev/null)
OLD_COUNT=$(echo "$OLD_FILES" | grep -c . 2>/dev/null || echo 0)
echo "  Found: $OLD_COUNT"
```

#### By TTL Expiry

```bash
echo ""
echo "Expired TTL:"
NOW=$(date +%s)
TTL_EXPIRED=""

for f in $(find "$HOME/.claude/mnemonic/$ORG" "./.claude/mnemonic" -name "*.memory.md" 2>/dev/null); do
    TTL=$(grep "^  ttl:" "$f" 2>/dev/null | sed 's/.*ttl: //')
    CREATED=$(grep "^created:" "$f" 2>/dev/null | sed 's/created: //')

    if [ -n "$TTL" ] && [ -n "$CREATED" ]; then
        # Parse TTL (simplified - handles P{N}D format)
        TTL_DAYS=$(echo "$TTL" | sed 's/P\([0-9]*\)D/\1/')
        if [ -n "$TTL_DAYS" ]; then
            # Calculate if expired (simplified check via file mtime)
            FILE_AGE=$(( ( NOW - $(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null) ) / 86400 ))
            if [ "$FILE_AGE" -gt "$TTL_DAYS" ]; then
                TTL_EXPIRED="$TTL_EXPIRED $f"
                echo "  $f (TTL: ${TTL_DAYS}d, Age: ${FILE_AGE}d)"
            fi
        fi
    fi
done

TTL_COUNT=$(echo "$TTL_EXPIRED" | wc -w | tr -d ' ')
echo "  Total: $TTL_COUNT"
```

#### By Decay Strength

```bash
echo ""
echo "Low strength (< $MIN_STRENGTH):"
LOW_STRENGTH=""

for f in $(find "$HOME/.claude/mnemonic/$ORG" "./.claude/mnemonic" -name "*.memory.md" 2>/dev/null); do
    STRENGTH=$(grep "strength:" "$f" 2>/dev/null | sed 's/.*strength: //')

    if [ -n "$STRENGTH" ]; then
        # Compare using Python for float comparison
        if python3 -c "exit(0 if float('$STRENGTH') < float('$MIN_STRENGTH') else 1)" 2>/dev/null; then
            LOW_STRENGTH="$LOW_STRENGTH $f"
            title=$(grep "^title:" "$f" 2>/dev/null | head -1 | sed 's/^title: "//' | sed 's/"$//')
            echo "  $title (strength: $STRENGTH)"
        fi
    fi
done

STRENGTH_COUNT=$(echo "$LOW_STRENGTH" | wc -w | tr -d ' ')
echo "  Total: $STRENGTH_COUNT"
```

### Step 3: Summarize

```bash
echo ""
echo "=== GC Summary ==="
ALL_CANDIDATES="$OLD_FILES $TTL_EXPIRED $LOW_STRENGTH"
TOTAL=$(echo "$ALL_CANDIDATES" | tr ' ' '\n' | sort -u | grep -c . 2>/dev/null || echo 0)
echo "Total candidates: $TOTAL"
```

### Step 3.5: Find Compression Candidates (if --compress)

Compression candidates are memories that:
- (Age > 30 days AND lines > COMPRESS_THRESHOLD) OR
- (strength < 0.3 AND lines > COMPRESS_THRESHOLD)

```bash
if [ "$COMPRESS" = "true" ] || [ "$COMPRESS_ONLY" = "true" ]; then
    COMPRESS_THRESHOLD="${COMPRESS_THRESHOLD:-100}"
    COMPRESS_CANDIDATES=""

    echo ""
    echo "=== Finding Compression Candidates ==="
    echo "Threshold: > $COMPRESS_THRESHOLD lines"

    for f in $(find "$HOME/.claude/mnemonic/$ORG" "./.claude/mnemonic" -name "*.memory.md" 2>/dev/null); do
        # Skip if already has summary
        if grep -q "^summary:" "$f" 2>/dev/null; then
            continue
        fi

        LINES=$(wc -l < "$f" | tr -d ' ')
        if [ "$LINES" -le "$COMPRESS_THRESHOLD" ]; then
            continue
        fi

        # Check age (> 30 days) or low strength (< 0.3)
        FILE_AGE=$(( ( $(date +%s) - $(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null) ) / 86400 ))
        STRENGTH=$(grep "strength:" "$f" 2>/dev/null | sed 's/.*strength: //')

        IS_CANDIDATE="false"
        if [ "$FILE_AGE" -gt 30 ]; then
            IS_CANDIDATE="true"
        fi
        if [ -n "$STRENGTH" ]; then
            if python3 -c "exit(0 if float('$STRENGTH') < 0.3 else 1)" 2>/dev/null; then
                IS_CANDIDATE="true"
            fi
        fi

        if [ "$IS_CANDIDATE" = "true" ]; then
            COMPRESS_CANDIDATES="$COMPRESS_CANDIDATES $f"
            title=$(grep "^title:" "$f" 2>/dev/null | head -1 | sed 's/^title: "//' | sed 's/"$//')
            echo "  $title ($LINES lines, ${FILE_AGE}d old)"
        fi
    done

    COMPRESS_COUNT=$(echo "$COMPRESS_CANDIDATES" | wc -w | tr -d ' ')
    echo "  Total compression candidates: $COMPRESS_COUNT"
fi
```

### Step 3.6: Compress Candidates (if --compress)

For each compression candidate, invoke the compression-worker agent to generate a summary.

```
For each file in COMPRESS_CANDIDATES:
  1. Invoke Task tool with compression-worker agent:
     - subagent_type: "mnemonic:compression-worker"
     - model: haiku
     - prompt: "Compress memory at {file_path}. Max 500 chars."

  2. Parse JSON response to get summary and keywords

  3. Insert summary into frontmatter (after provenance):
     - Add: summary: "{summary}"
     - Add: compressedAt: {timestamp}   (MIF 1.4.1; never the legacy compressed_at)

  4. Optionally add new keywords to tags
```

**Frontmatter Update Pattern:**

```bash
# Insert summary after provenance section
# Look for the line after "provenance:" block ends
# Add:
#   summary: "The generated summary text"
#   compressedAt: 2026-01-24T10:00:00Z
```

**Example:**

```yaml
# Before:
provenance:
  sourceType: agent_inferred
  agent: claude-opus-4
  confidence: 0.95
---

# After:
provenance:
  sourceType: agent_inferred
  agent: claude-opus-4
  confidence: 0.95
summary: "Chose PostgreSQL for storage due to JSON support and ACID compliance. Key factors: team expertise and proven scalability."
compressedAt: 2026-01-24T10:00:00Z
---
```

### Step 3.7: Handle --compress-only

If `--compress-only` is set, skip archive/delete steps:

```bash
if [ "$COMPRESS_ONLY" = "true" ]; then
    echo ""
    echo "=== Compress-Only Mode ==="
    echo "Compressed: $COMPRESS_COUNT memories"
    echo "Skipping archive/delete steps"

    # Commit compression changes
    cd "$HOME/.claude/mnemonic"
    git add -A
    git commit -m "GC: Compressed $COMPRESS_COUNT memories"
    cd -

    echo ""
    echo "=== GC Complete (Compress Only) ==="
    exit 0
fi
```

### Step 4: Confirm and Execute

```bash
if [ "$DRY_RUN" = "true" ]; then
    echo ""
    echo "[DRY RUN] No changes made"
    exit 0
fi

if [ "$FORCE" != "true" ] && [ "$TOTAL" -gt 0 ]; then
    echo ""
    echo "Proceed with garbage collection? (y/N)"
    # Wait for confirmation in interactive mode
fi
```

### Step 5: Archive or Delete

```bash
if [ "$ARCHIVE" = "true" ]; then
    echo ""
    echo "Archiving to: $ARCHIVE_DIR"
    mkdir -p "$ARCHIVE_DIR"

    for f in $(echo "$ALL_CANDIDATES" | tr ' ' '\n' | sort -u); do
        [ -f "$f" ] || continue
        mv "$f" "$ARCHIVE_DIR/"
        echo "  Archived: $(basename "$f")"
    done
else
    echo ""
    echo "Deleting:"

    for f in $(echo "$ALL_CANDIDATES" | tr ' ' '\n' | sort -u); do
        [ -f "$f" ] || continue
        rm "$f"
        echo "  Deleted: $(basename "$f")"
    done
fi
```

### Step 6: Update Decay Scores

```bash
echo ""
echo "Updating decay scores..."

for f in $(find "$HOME/.claude/mnemonic/$ORG" "./.claude/mnemonic" -name "*.memory.md" 2>/dev/null); do
    # MIF 1.4.1 keys (lastAccessed, halfLife) or legacy (last_accessed, half_life)
    LAST_ACCESS=$(grep -E "(lastAccessed|last_accessed):" "$f" 2>/dev/null | head -1 | sed -E 's/.*(lastAccessed|last_accessed): //')
    HALF_LIFE=$(grep -E "(halfLife|half_life):" "$f" 2>/dev/null | head -1 | sed -E 's/.*(halfLife|half_life): //')
    CURRENT_STRENGTH=$(grep "strength:" "$f" 2>/dev/null | sed 's/.*strength: //')

    if [ -n "$LAST_ACCESS" ] && [ -n "$HALF_LIFE" ] && [ -n "$CURRENT_STRENGTH" ]; then
        # Calculate new strength based on decay model
        # new_strength = current_strength * (0.5 ^ (days_since_access / half_life_days))
        # (Simplified: just log that update would happen)
        :
    fi
done
```

### Step 7: Commit Changes

```bash
echo ""
echo "Committing changes..."
cd "$HOME/.claude/mnemonic"
git add -A
git commit -m "GC: Archived/removed $TOTAL memories"
cd -

echo ""
echo "=== GC Complete ==="
echo "Processed: $TOTAL memories"
```

## Example Usage

```bash
# Preview what would be collected
/mnemonic:gc --dry-run

# Archive expired memories
/mnemonic:gc --archive

# Force delete without confirmation
/mnemonic:gc --force

# Custom thresholds
/mnemonic:gc --min-strength 0.2 --max-age 180

# Delete instead of archive
/mnemonic:gc --archive=false --force
```

## Output

Displays:
- Candidates by category (old, TTL expired, low strength)
- Total count
- Actions taken (archive/delete)
- Git commit status
