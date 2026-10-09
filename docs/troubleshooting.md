# Troubleshooting Guide

Common issues and solutions for Mnemonic.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Hook Failures](#hook-failures)
- [Search Not Finding Memories](#search-not-finding-memories)
- [Git Remote Detection Issues](#git-remote-detection-issues)
- [Ontology Validation Errors](#ontology-validation-errors)
- [Memory File Errors](#memory-file-errors)
- [Performance Issues](#performance-issues)
- [Relationship Issues](#relationship-issues)

## Installation Issues

### Plugin Not Loading

**Symptom:** Claude Code doesn't recognize mnemonic commands.

**Solution:**

````bash
# Check plugin directory
claude settings plugins list

# Add plugin if missing
claude settings plugins add /path/to/mnemonic

# Verify plugin.json exists
ls -la /path/to/mnemonic/.claude-plugin/plugin.json
````

### Missing Dependencies

**Symptom:** Commands fail with "command not found" errors.

**Solution:**

````bash
# Check dependencies
make check-deps

# Install missing tools
# macOS
brew install ripgrep yq

# Ubuntu/Debian
apt install ripgrep
snap install yq

# Verify Python version (3.8+)
python3 --version
````

### Permission Errors

**Symptom:** "Permission denied" when creating memories.

**Solution:**

````bash
# Check directory permissions
ls -la ~/.claude/mnemonic/

# Fix permissions
chmod 755 ~/.claude/mnemonic/
chmod 644 ~/.claude/mnemonic/**/*.memory.md
````

## Hook Failures

### SessionStart Hook Errors

**Symptom:** Session doesn't show memory status on startup.

**Solution:**

````bash
# Check hook execution permissions
ls -la /path/to/mnemonic/hooks/session_start.py

# Make executable
chmod +x /path/to/mnemonic/hooks/session_start.py

# Test hook manually
python3 /path/to/mnemonic/hooks/session_start.py --test
````

### PreToolUse Hook Not Finding Memories

**Symptom:** No memory suggestions when editing files.

**Solution:**

1. **Verify git remote exists:**
   ````bash
   git remote -v
   ````

2. **Check ontology file:**
   ````bash
   cat .claude/mnemonic/ontology.yaml
   ````

3. **Test file context detection:**
   ````python
   from lib.ontology import load_file_patterns
   from lib.search import detect_file_context
   
   patterns = load_file_patterns()
   context = detect_file_context("path/to/file.py", patterns)
   print(context)
   ````

### PostToolUse Hook Errors

**Symptom:** Automatic capture not working.

**Solution:**

````bash
# Check hook is enabled
grep -A 5 "PostToolUse" /path/to/mnemonic/hooks/hooks.json

# Test hook manually
echo '{"tool": "Edit", "result": "success"}' | \
  python3 /path/to/mnemonic/hooks/post_tool_use.py
````

## Search Not Finding Memories

### Ripgrep Not Installed

**Symptom:** `/mnemonic:search` fails or returns no results.

**Solution:**

````bash
# Install ripgrep
# macOS
brew install ripgrep

# Ubuntu/Debian
apt install ripgrep

# Verify installation
rg --version
````

### Wrong Search Path

**Symptom:** Search works but returns nothing.

**Solution:**

````bash
# Check MNEMONIC_ROOT environment variable
echo $MNEMONIC_ROOT

# Check actual memory location
find ~ -name "*.memory.md" -type f | head -5

# Verify memory root in config (XDG)
cat ~/.config/mnemonic/config.json
````

### Case Sensitivity

**Symptom:** Search only finds exact case matches.

**Solution:**

Use case-insensitive search:

````bash
# With ripgrep
rg -i "search term" $MNEMONIC_ROOT --glob "*.memory.md"

# With /mnemonic:search
/mnemonic:search --ignore-case "search term"
````

## Git Remote Detection Issues

### No Git Remote

**Symptom:** Memories stored in `default/` instead of org/project structure.

**Solution:**

````bash
# Add git remote
git remote add origin https://github.com/org/project.git

# Verify detection
python3 -c "from lib.paths import PathContext; print(PathContext.detect())"
````

### SSH Remote Format Not Recognized

**Symptom:** Organization not detected from SSH remote URL.

**Solution:**

````bash
# Current remote
git remote get-url origin
# Example: git@github.com:org/project.git

# Add HTTPS remote (preferred for detection)
git remote set-url origin https://github.com/org/project.git

# Or fix SSH parsing in lib/paths.py (already handles SSH format)
````

### Multiple Remotes

**Symptom:** Wrong remote detected.

**Solution:**

````bash
# Check all remotes
git remote -v

# Ensure 'origin' points to correct repository
git remote set-url origin https://github.com/correct-org/project.git
````

## Ontology Validation Errors

### Invalid YAML Syntax

**Symptom:** Ontology loading fails with YAML parse error.

**Solution:**

````bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('.claude/mnemonic/ontology.yaml'))"

# Validate ontology file
/mnemonic:validate .claude/mnemonic/ontology.yaml
````

### Missing Required Fields

**Symptom:** "Missing required field" error when loading ontology.

**Solution:**

Check ontology against schema:

````yaml
# Required fields
name: my-ontology
version: 1.0.0
namespaces:
  - name: semantic
    sub_namespaces: [...]
entity_types: [...]
relationship_types: [...]
````

See [docs/ontologies.md](ontologies.md) for complete schema.

### Invalid Entity Type

**Symptom:** Entity discovery fails or ignores certain patterns.

**Solution:**

````yaml
# Verify entity_types structure
entity_types:
  - name: component         # Must be lowercase, hyphenated
    namespace: semantic/entities
    description: "..."
    traits:
      - persistent
      - versioned
````

### Pattern Matching Issues

**Symptom:** File patterns not detecting files.

**Solution:**

Test pattern matching:

````bash
# Test file pattern
python3 << 'EOF'
import re
pattern = r'\.ya?ml$'
test_file = "config.yaml"
print(re.search(pattern, test_file))
EOF
````

## Memory File Errors

### Invalid Frontmatter

**Symptom:** Memory file rejected or not found in search.

**Solution:**

Validate frontmatter:

````bash
# Use validation tool
python3 tools/mnemonic-validate /path/to/memory.memory.md

# Check required fields
# - id (valid UUID)
# - type (semantic|episodic|procedural)
# - namespace
# - created (ISO 8601 timestamp)
# - title
````

### Malformed UUID

**Symptom:** "Invalid UUID format" error.

**Solution:**

````bash
# Generate valid UUID
uuidgen
# OR
python3 -c "import uuid; print(uuid.uuid4())"

# UUID format: 550e8400-e29b-41d4-a716-446655440000
````

### Invalid Timestamp

**Symptom:** "Invalid timestamp format" error.

**Solution:**

Use ISO 8601 format:

````bash
# Generate timestamp
date -u +"%Y-%m-%dT%H:%M:%SZ"
# OR
python3 -c "from datetime import datetime; print(datetime.utcnow().isoformat() + 'Z')"

# Format: 2026-02-16T17:00:00Z
````

### Duplicate IDs

**Symptom:** Relationship linking fails or search returns wrong memories.

**Solution:**

````bash
# Find duplicate IDs
find $MNEMONIC_ROOT -name "*.memory.md" -exec grep -H "^id:" {} \; | \
  awk -F: '{print $3}' | sort | uniq -d

# Regenerate IDs for duplicates
python3 << 'EOF'
import uuid
print(f"New ID: {uuid.uuid4()}")
EOF
````

## Performance Issues

### Slow Search

**Symptom:** Search takes several seconds.

**Solution:**

1. **Use ripgrep instead of grep:**
   ````bash
   # Fast
   rg "search term" $MNEMONIC_ROOT --glob "*.memory.md"
   
   # Slow
   grep -r "search term" $MNEMONIC_ROOT
   ````

2. **Limit search scope:**
   ````bash
   # Search specific namespace only
   rg "term" $MNEMONIC_ROOT/*/_semantic/decisions --glob "*.memory.md"
   ````

3. **Use indexed search:**
   ````bash
   # Build git grep index (if using git)
   cd $MNEMONIC_ROOT
   git grep "search term" -- "*.memory.md"
   ````

### Large Memory Repository

**Symptom:** Operations slow with thousands of memories.

**Solution:**

Run garbage collection:

````bash
# Preview which memories would be collected
/mnemonic:gc --dry-run

# Compress memories to save space
/mnemonic:gc --compress

# Archive memories instead of deleting them
/mnemonic:gc --archive
````

### Hook Timeout

**Symptom:** Session startup slow or times out.

**Solution:**

Disable expensive hooks temporarily:

````bash
# Edit hooks/hooks.json
# Set enabled: false for slow hooks

# Or reduce hook verbosity
export MNEMONIC_HOOK_QUIET=1
````

## Relationship Issues

### Broken Links

**Symptom:** Relationship points to non-existent memory.

**Solution:**

````bash
# Validate all relationships
/mnemonic:custodian validate-links

# Fix broken links automatically
/mnemonic:custodian validate-links --fix
````

### Missing Inverse Relationships

**Symptom:** Relationship exists in one direction only.

**Solution:**

Add bidirectional relationships using the library helper:

````bash
# Add a bidirectional relationship using the library helper
python3 << 'EOF'
from lib.relationships import add_bidirectional_relationship

add_bidirectional_relationship(
    source_path="/path/to/source.memory.md",
    target_path="/path/to/target.memory.md",
    rel_type="relates-to"
)
EOF
````

### Invalid Relationship Type

**Symptom:** "Unknown relationship type" error.

**Solution:**

````python
from lib.relationships import get_all_valid_types

# Check valid types
valid_types = get_all_valid_types()
print(valid_types)

# Use valid type from ontology
````

Valid default types (MIF 1.4.2 token / registry name; legacy snake_case
spellings such as `relates_to` are still accepted on read):
- `relates-to` / `RelatesTo`
- `derived-from` / `DerivedFrom` (inverse: `derives`)
- `supersedes` / `Supersedes` (inverse: `superseded-by`)
- `conflicts-with` / `ConflictsWith`
- `part-of` / `PartOf` (inverse: `contains`)
- `uses` / `Uses` (inverse: `used-by`)
- `implements` / `Implements` (inverse: `implemented-by`)
- `created` / `Created` (inverse: `created-by`)
- `mentioned-in` / `MentionedIn` (inverse: `mentions`)

## Getting Help

### Capture Command Output

You can capture detailed output from Mnemonic commands and include it when reporting issues.

````bash
# Capture detailed output from a Mnemonic command
/mnemonic:status 2>&1 | tee mnemonic-debug.log
````

### Test Hook in Isolation

````bash
# Run hook with test flag
python3 hooks/session_start.py --test

# Check exit code
echo $?
````

### Validate Entire System

````bash
# Run comprehensive validation
make validate

# Run tests
make test

# Check linting
make lint
````

### Report Issues

When reporting issues, include:

1. **Version information:**
   ````bash
   claude --version
   python3 --version
   rg --version
   ````

2. **Configuration:**
   ````bash
   cat ~/.config/mnemonic/config.json
   git remote -v
   ````

3. **Error output:**
   ````bash
   /mnemonic:command 2>&1 | tee error.log
   ````

4. **Memory structure:**
   ````bash
   tree -L 3 $MNEMONIC_ROOT
   ````

## See Also

- [Installation](../README.md#installation) - Setup instructions
- [CLI Usage](cli-usage.md) - Command-line operations
- [Validation](validation.md) - Memory validation guide
- [Contributing](../CONTRIBUTING.md) - Development setup
