# Mnemonic Library Reference

Comprehensive reference for the mnemonic Python library modules.

## Table of Contents

- [Overview](#overview)
- [Core Modules](#core-modules)
  - [paths](#paths) - Path resolution and filesystem layout
  - [config](#config) - Configuration management
  - [memory_reader](#memory_reader) - Memory file parsing
  - [migrate_filenames](#migrate_filenames) - Memory file migration utilities
  - [search](#search) - Memory search and ranking
  - [relationships](#relationships) - Relationship types and linking
  - [ontology](#ontology) - Custom ontology support
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)

## Overview

The `lib/` directory contains shared Python utilities used across mnemonic's hooks, commands, and tools. All modules are designed for:

- **Testability**: Dependency injection with optional resolvers
- **Type Safety**: Full Python type hints (3.8+)
- **Pure Functions**: Minimal side effects, clear inputs/outputs
- **Documentation**: Comprehensive docstrings

## Core Modules

### paths

**File**: `lib/paths.py`

Centralized path resolution for all mnemonic memory operations. Provides single source of truth for memory directories, search paths, and blackboard locations.

**Key Classes**:
- `PathResolver` - Main path computation engine
- `PathContext` - Environment context (`org`, `project`, `home_dir`, `project_dir`, `memory_root`, `scheme`)
- `PathScheme` - Path scheme enum (LEGACY, V2)
- `Scope` - Memory scope enum (USER, PROJECT, ORG)

**Quick Example**:
````python
from lib.paths import PathResolver, Scope

resolver = PathResolver()
memory_dir = resolver.get_memory_dir("_semantic/decisions", Scope.PROJECT)
memory_dir.mkdir(parents=True, exist_ok=True)
````

**See Also**: [ADR-009: Unified Path Resolution](adrs/adr-009-unified-path-resolution.md)

---

### config

**File**: `lib/config.py`

Configuration management for mnemonic memory store location. Reads/writes `~/.config/mnemonic/config.json` (XDG-compliant).

**Key Functions**:
````python
from lib.config import get_memory_root, MnemonicConfig

# Get configured memory root (most common usage)
root = get_memory_root()  # Returns Path

# Advanced: Load and modify config
config = MnemonicConfig.load()
config.memory_store_path  # Returns expanded Path
config.memory_store_path_raw  # Returns raw string

# Save new config
new_config = MnemonicConfig(memory_store_path="~/custom/path")
new_config.save()
````

**Config Schema**:
````json
{
  "version": "1.0",
  "memory_store_path": "~/.claude/mnemonic"
}
````

**Default Values**:
- Config file: `~/.config/mnemonic/config.json`
- Default memory root: `~/.claude/mnemonic`
- Config version: `1.0`

**Design Notes**:
- Fixed config location (XDG-compliant, not configurable)
- Tilde expansion handled automatically
- Returns default config if file missing or invalid
- Thread-safe read operations

---

### memory_reader

**File**: `lib/memory_reader.py`

Memory file parsing for extracting frontmatter metadata and generating summaries. Used by hooks to inject memory context.

**Key Functions**:

````python
from lib.memory_reader import get_memory_metadata, get_memory_summary

# Get full frontmatter metadata
metadata = get_memory_metadata("memory.memory.md")
# Returns: {'id': '...', 'title': '...', 'namespace': '...', 'tags': [...], 'relationships': [...], 'summary': '...', 'path': '...'}

# Get memory summary (title and first paragraph)
summary_info = get_memory_summary("memory.memory.md", max_summary=300)
# Returns: {"title": "My Decision", "summary": "First paragraph of content..."}
````

**Parsing Strategy**:
1. **PyYAML** (if available): Full YAML parsing with proper type handling
2. **Regex fallback**: Lightweight parsing when PyYAML unavailable
   - Extracts: `id`, `title`, `type`, `namespace`, `tags`
   - Handles inline lists: `tags: [a, b, c]`
   - Handles multi-line lists: `tags:\n  - a\n  - b`
   - Parses relationship blocks

**API Reference**:

#### `get_memory_metadata(path: str, max_summary: int = 300) -> Optional[dict]`
Extract frontmatter as dictionary.

**Returns**:
- `id` (str): UUID
- `title` (str): Memory title
- `namespace` (str): Namespace path
- `tags` (list): Tag list
- `relationships` (list): Relationship objects
- `summary` (str): First paragraph summary
- `path` (str): Absolute path to memory file

Returns None if file doesn't exist or can't be read.

#### `get_memory_summary(path: str, max_summary: int = 300) -> dict`
Extract title and summary from memory file.

**Returns**:
Dictionary with keys:
- `title` (str): Memory title from frontmatter or filename
- `summary` (str): First paragraph after frontmatter (truncated to max_summary)

**Design Notes**:
- Graceful degradation (YAML → regex fallback)
- No exceptions raised on parse errors
- Returns empty dict/string on failure
- Used by hooks for `additionalContext` injection

---

### migrate_filenames

**File**: `lib/migrate_filenames.py`

Migration utilities for transitioning memory files from `{uuid}-{slug}.memory.md` to `{slug}.memory.md` naming convention. Handles collision detection, content merging, and idempotent execution.

**Key Functions**:

````python
from lib.migrate_filenames import migrate_all, is_migration_complete, migrate_file
from pathlib import Path

# Check if migration already completed
memory_root = Path.home() / ".claude" / "mnemonic"
if not is_migration_complete(memory_root):
    # Perform dry run first
    results = migrate_all(memory_root, dry_run=True)
    print(f"Would migrate {len(results)} files")
    
    # Execute migration
    results = migrate_all(memory_root, dry_run=False)
    for result in results:
        print(f"{result.action}: {result.original.name} → {result.target.name}")
````

**Migration Behavior**:
- **Rename**: `{uuid}-decision.memory.md` → `decision.memory.md` (preserves git history)
- **Merge**: If `decision.memory.md` already exists, merges content from UUID-prefixed file
- **Idempotent**: Marks completion with `.migration_slug_only_complete` marker file

**API Reference**:

#### `migrate_all(mnemonic_root: Path, dry_run: bool = False) -> list[MigrationResult]`
Migrate all UUID-prefixed memory files in directory tree.

**Parameters**:
- `mnemonic_root`: Root directory to scan recursively
- `dry_run`: If True, return results without modifying files

**Returns**: List of `MigrationResult` objects with fields:
- `original` (Path): Source file path
- `target` (Path): Destination file path
- `action` (str): One of "renamed", "merged", "skipped"
- `merged_with` (Optional[Path]): Target file if merged

**Behavior**:
- Skips if `.migration_slug_only_complete` marker exists
- Uses `git mv` when possible to preserve history
- Merges content on collision (appends under "Merged Content" heading)
- Creates marker file on completion

#### `migrate_file(file_path: Path, dry_run: bool = False) -> MigrationResult`
Migrate a single memory file.

**Parameters**:
- `file_path`: Path to memory file
- `dry_run`: If True, return result without modifying files

**Returns**: `MigrationResult` object

**Collision Handling**:
When target file exists, merges content by:
1. Keeping existing frontmatter (preserves original ID, dates)
2. Appending incoming body under separator
3. Adding provenance note with incoming UUID

#### `is_migration_complete(mnemonic_root: Path) -> bool`
Check if migration has been run.

**Returns**: True if `.migration_slug_only_complete` marker exists

#### `mark_migration_complete(mnemonic_root: Path) -> None`
Create marker file to prevent re-running migration.

**Use Cases**:
- **Batch Migration**: Run once during setup to clean up legacy filenames
- **Continuous Integration**: Check `is_migration_complete()` before operations
- **Manual Recovery**: Use `migrate_file()` for selective migration after conflicts

**Example - Bulk Migration**:

````python
from lib.migrate_filenames import migrate_all, migration_summary
from pathlib import Path

memory_root = Path("~/.claude/mnemonic").expanduser()

# Execute with logging
results = migrate_all(memory_root, dry_run=False)
summary = migration_summary(results)

print(f"Migration complete:")
print(f"  Renamed: {summary['renamed']} files")
print(f"  Merged: {summary['merged']} files")
print(f"  Skipped: {summary['skipped']} files")
````

**Design Notes**:
- Atomic writes via `.tmp` files to prevent corruption
- Git-aware (uses `git mv` when possible)
- Collision-safe (merges rather than overwrites)
- Idempotent by default (marker file prevents re-runs)
- CLI support: `python -m lib.migrate_filenames --dry-run`

---

### search

**File**: `lib/search.py`

Centralized memory search logic with scoring, ranking, and context detection. Consolidates search functions from all hooks.

**Search Functions**:

````python
from lib.search import (
    search_memories,
    find_related_memories_scored,
    find_memories_for_context,
    detect_file_context,
    extract_topic
)

# 1. Basic keyword search
results = search_memories("authentication", max_results=5)
# Returns: list of Path objects

# 2. Scored semantic search
scored = find_related_memories_scored(
    title="API Authentication Design",
    tags=["security", "api"],
    namespace="_semantic/decisions",
    content_keywords=["JWT", "OAuth"],
    max_results=10
)
# Returns: list of (Path, score) tuples, sorted by relevance

# 3. File context detection
context = detect_file_context("src/auth/login.py")
# Returns: dict with namespace, tags, keywords

# 4. Topic extraction from prompt
topic = extract_topic("How do we handle user authentication?")
# Returns: "user authentication"
````

**Scoring Algorithm**:

Memories are scored based on multiple signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| Same cognitive type | 30 | Both in `_semantic/*`, `_episodic/*`, etc. |
| Exact namespace match | 20 | Same sub-namespace (e.g., `decisions`) |
| Tag overlap | 20/tag | Shared tags |
| Title keyword match | 15/keyword | Keywords in title |
| Content keyword match | 5/keyword | Keywords in body |

**Minimum threshold**: 15 points (configurable via `SCORE_MIN_THRESHOLD`)

**API Reference**:

#### `search_memories(topic: str, max_results: int = 3) -> list[Path]`
Basic ripgrep search across all memory roots.

**Args**:
- `topic`: Search keywords
- `max_results`: Maximum results to return

**Returns**: List of absolute paths to matching `.memory.md` files

---

#### `find_related_memories_scored(...) -> list[tuple[Path, int]]`
Semantic search with relevance scoring.

**Args**:
- `title`: Reference memory title
- `tags`: Reference tags list
- `namespace`: Reference namespace
- `content_keywords`: Additional keywords
- `max_results`: Maximum results

**Returns**: List of (path, score) tuples, sorted by score descending

**Example**:
````python
results = find_related_memories_scored(
    title="PostgreSQL migration",
    tags=["database", "migration"],
    namespace="_procedural/migrations",
    content_keywords=["schema", "version"],
    max_results=5
)

for path, score in results:
    print(f"{score:3d} - {path.name}")
# Output:
#  65 - postgres-upgrade-v14.memory.md
#  50 - database-schema-changes.memory.md
#  35 - migration-rollback-procedure.memory.md
````

---

#### `detect_file_context(filepath: str) -> dict`
Infer namespace and tags from file path.

**Pattern Detection**:
- Authentication: `auth`, `login`, `jwt`, `oauth`
- API: `api`, `endpoint`, `route`, `controller`
- Database: `db`, `model`, `schema`, `migration`
- Testing: `test`, `spec`, `__tests__`
- Security: `security`, `crypto`, `hash`
- Configuration: `config`, `settings`, `.env`

**Returns**:
````python
{
    'namespace': str,  # Inferred namespace
    'tags': list,      # Suggested tags
    'keywords': list   # Extracted keywords
}
````

---

#### `extract_topic(prompt: str) -> str`
Extract searchable topic from user prompt.

**Processing**:
1. Remove stopwords (the, a, is, etc.)
2. Extract keywords
3. Normalize spacing
4. Limit to reasonable length

**Example**:
````python
extract_topic("What is our authentication strategy?")
# Returns: "authentication strategy"

extract_topic("How do we deploy to production?")
# Returns: "deploy production"
````

**Design Notes**:
- All search uses `ripgrep` for speed
- Searches across all memory roots (user + project)
- Case-insensitive matching
- Graceful fallback if ripgrep unavailable
- No exceptions on search failures

---

### relationships

**File**: `lib/relationships.py`

MIF-compliant relationship type registry and bidirectional linking. Implements MIF Section 8.2 relationship semantics.

**Relationship Types** (MIF Section 8.2):

| PascalCase | Inverse | Symmetric | Use Case |
|------------|---------|-----------|----------|
| `RelatesTo` | `RelatesTo` | ✓ | General association |
| `DerivedFrom` | `Derives` | ✗ | Conclusions from evidence |
| `Supersedes` | `SupersededBy` | ✗ | Decision evolution |
| `ConflictsWith` | `ConflictsWith` | ✓ | Contradictory information |
| `PartOf` | `Contains` | ✗ | Hierarchical structure |
| `Implements` | `ImplementedBy` | ✗ | Spec to implementation |
| `Uses` | `UsedBy` | ✗ | Dependency tracking |
| `Created` | `CreatedBy` | ✗ | Provenance |
| `MentionedIn` | `Mentions` | ✗ | Cross-references |

**Quick Example**:
````python
from lib.relationships import add_bidirectional_relationship

# Add bidirectional link
add_bidirectional_relationship(
    source_path="decision-a.memory.md",
    target_path="decision-b.memory.md",
    rel_type="supersedes",  # kebab-case, snake_case or PascalCase
    label="Replaced by new approach"
)

# Creates (MIF 1.4.2 form):
# - decision-a.memory.md: supersedes -> urn:mif:<decision-b uuid>
# - decision-b.memory.md: superseded-by -> urn:mif:<decision-a uuid>
````

**API Reference**:

#### `add_relationship(memory_path, rel_type, target_id, label=None, target_title=None)`
Add a single relationship in MIF 1.4.2 form: a frontmatter entry
(`type: <kebab-case>`, `target: urn:mif:<uuid>`, optional `metadata.label`)
plus its body mirror line `- <type> [<target_title>](urn:mif:<uuid>)` under
`## Relationships`.

**Args**:
- `memory_path` (str): Memory file to modify
- `rel_type` (str): Relationship type (kebab-case, snake_case or PascalCase)
- `target_id` (str): Target memory UUID (or `urn:mif:` id)
- `label` (str, optional): Human-readable description (`metadata.label`)
- `target_title` (str, optional): Link text for the body mirror line

**Validation**:
- Checks type is valid via `is_valid_type()`
- Prevents duplicate relationships, treating legacy spellings
  (`relates_to`, bare-UUID targets, `[[uuid]]` body lines) as duplicates

---

#### `add_bidirectional_relationship(source_path, target_path, rel_type, label=None) -> tuple[bool, bool]`
Add bidirectional relationship pair.

**Args**:
- `source_path` (str): Source memory file path
- `target_path` (str): Target memory file path
- `rel_type` (str): Relationship type (kebab-case, snake_case or PascalCase)
- `label` (str, optional): Human-readable description

**Returns**:
Tuple of (forward_success, inverse_success) booleans.

**Automatic Inverse**:
- `supersedes` → creates `superseded-by` back-reference
- `relates-to` → creates `relates-to` (symmetric)
- `derived-from` → creates `derives` back-reference

**Example**:
````python
# Link new decision to old one
add_bidirectional_relationship(
    source_path="new-approach.memory.md",
    target_path="old-approach.memory.md",
    rel_type="supersedes"
)

# Frontmatter updates:
# new-approach.memory.md:
#   relationships:
#     - type: supersedes
#       target: urn:mif:<old-uuid>
#
# old-approach.memory.md:
#   relationships:
#     - type: superseded-by
#       target: urn:mif:<new-uuid>
#
# Each file also gains a body line under "## Relationships", e.g.
#   - supersedes [Old Approach](urn:mif:<old-uuid>)
````

---

#### Type Helpers

````python
from lib.relationships import (
    to_pascal,
    to_snake,
    to_token,
    get_inverse,
    is_valid_type,
    is_symmetric,
    get_all_valid_types
)

# Convert naming
to_pascal("supersedes")        # → "Supersedes"
to_snake("SupersededBy")       # → "superseded_by"
to_token("SupersededBy")       # → "superseded-by" (MIF 1.4.2 written form)

# Get inverse
get_inverse("Supersedes")      # → "SupersededBy"
get_inverse("RelatesTo")       # → "RelatesTo" (symmetric)

# Validate
is_valid_type("Supersedes")    # → True
is_valid_type("Invalid")       # → False

# Check symmetry
is_symmetric("RelatesTo")      # → True
is_symmetric("Supersedes")     # → False

# Get all types
get_all_valid_types()
# → {'RelatesTo', 'Supersedes', 'SupersededBy', ...}
````

**Design Notes**:
- MIF 1.4.2 sections 8.1.1 / 8.2 compliant
- Written form is the kebab-case token (`superseded-by`); PascalCase is the
  registry/display name
- PascalCase and snake_case are accepted on input for backward compatibility
- Automatic bidirectional linking
- Validation prevents invalid relationships
- Used by capture workflow, gc compression, custodian

---

### ontology

**File**: `lib/ontology.py`

Custom ontology loading and validation. Supports namespace hierarchies, entity types, and discovery patterns.

**Key Functions**:

````python
from lib.ontology import (
    load_ontology_data,
    load_ontology_namespaces,
    validate_memory_against_ontology,
    get_ontology_file
)

# Load ontology YAML
ontology = load_ontology_data()
# Returns: dict with namespaces, entities, relationships, discovery

# Get namespace hierarchy
namespaces = load_ontology_namespaces()
# Returns: dict mapping namespace -> metadata

# Validate memory
is_valid, errors = validate_memory_against_ontology(
    memory_type="semantic",
    namespace="_semantic/decisions"
)

# Get ontology file path
ontology_path = get_ontology_file()
# Currently resolves to the built-in fallback ontology file:
# skills/ontology/fallback/ontologies/mif-base.ontology.yaml
````

**Ontology Resolution**:

Currently, `get_ontology_file()` resolves only the built-in fallback ontology:

1. Fallback: `skills/ontology/fallback/ontologies/mif-base.ontology.yaml`

Project-level (`.claude/mnemonic/ontology.yaml`) and user-level
(`~/.claude/mnemonic/ontology.yaml`) ontology files are not currently
used in the resolution process and may be supported in a future version.

**Example Ontology**:
````yaml
namespaces:
  - id: semantic/decisions
    type: semantic
    description: Architectural choices and rationale
    retention_days: 365
    
  - id: semantic/knowledge/security
    type: semantic
    description: Security policies and practices
    retention_days: 180

entities:
  - type: technology
    schema:
      - field: name
        required: true
      - field: version
        required: false
    namespaces: [semantic/entities]

relationships:
  - type: depends_on
    description: Technical dependency
    
discovery:
  file_patterns:
    - pattern: "auth|login"
      suggest_namespace: semantic/knowledge/security
      suggest_tags: [authentication]
````

**API Reference**:

#### `load_ontology_data() -> dict`
Load ontology YAML with precedence.

**Returns**: Complete ontology dict or default if not found

---

#### `validate_memory_against_ontology(memory_type, namespace) -> tuple[bool, list]`
Validate memory conforms to loaded ontology.

**Returns**: `(is_valid, error_messages)`

---

**See Also**:
- [Ontologies Guide](ontologies.md)
- [ADR-008: Custom Ontologies](adrs/adr-008-custom-ontologies.md)
- [Ontology Skill](../skills/ontology/SKILL.md)

---

## Installation

The library is included with mnemonic and requires no separate installation.

**Dependencies**:
- Python 3.8+
- PyYAML (optional but recommended for memory_reader)

````bash
# Install optional dependencies
pip install pyyaml

# Or use project requirements
pip install -r requirements.txt  # if available
````

## Quick Start

### Basic Import Pattern

````python
# Recommended: import specific functions
from lib.paths import PathResolver, Scope
from lib.search import search_memories
from lib.memory_reader import get_memory_summary

# Alternative: import lib module
import lib
resolver = lib.PathResolver()
````

### Common Usage Pattern

````python
from pathlib import Path
from lib.paths import PathResolver, Scope
from lib.search import find_related_memories_scored
from lib.memory_reader import get_memory_summary

# Initialize
resolver = PathResolver()

# Find related memories
results = find_related_memories_scored(
    title="API Authentication",
    tags=["security", "api"],
    namespace="_semantic/decisions"
)

# Read summaries
for path, score in results[:3]:
    summary = get_memory_summary(path)
    print(f"[{score}] {summary['title']}: {summary['summary']}\n")
````

### Testing Pattern

````python
import pytest
from pathlib import Path
from lib.paths import PathResolver, PathContext, PathScheme

@pytest.fixture
def test_resolver(tmp_path):
    """Isolated resolver for testing."""
    context = PathContext(
        org="testorg",
        project="testproject",
        home_dir=tmp_path / "home",
        project_dir=tmp_path / "project",
        memory_root=tmp_path / "mnemonic",
        scheme=PathScheme.LEGACY
    )
    return PathResolver(context)

def test_memory_operations(test_resolver):
    memory_dir = test_resolver.get_memory_dir("_semantic/decisions", Scope.PROJECT)
    assert memory_dir.parent.name == "mnemonic"
````

## API Reference

### Module Index

| Module | Primary Use Case | Key Functions |
|--------|------------------|---------------|
| `paths.py` | Path resolution | `get_memory_dir()`, `get_search_paths()` |
| `config.py` | Configuration | `get_memory_root()`, `MnemonicConfig.load()` |
| `memory_reader.py` | Parsing | `get_memory_metadata()`, `get_memory_summary()` |
| `migrate_filenames.py` | File migration | `migrate_all()`, `migrate_file()`, `is_migration_complete()` |
| `search.py` | Search/ranking | `search_memories()`, `find_related_memories_scored()` |
| `relationships.py` | Linking | `add_bidirectional_relationship()`, `get_inverse()` |
| `ontology.py` | Validation | `load_ontology_data()`, `validate_memory_against_ontology()` |

### Import Cheat Sheet

````python
# Paths
from lib.paths import PathResolver, Scope, get_memory_dir

# Config
from lib.config import get_memory_root

# Memory reading
from lib.memory_reader import get_memory_metadata, get_memory_summary

# Migration
from lib.migrate_filenames import migrate_all, is_migration_complete

# Search
from lib.search import search_memories, find_related_memories_scored

# Relationships
from lib.relationships import add_bidirectional_relationship, get_inverse

# Ontology
from lib.ontology import load_ontology_data, validate_memory_against_ontology
````

## Related Documentation

- [Architecture](architecture.md) - System design overview
- [CLI Usage](cli-usage.md) - Command-line operations
- [Validation](validation.md) - MIF schema validation
- [Ontologies](ontologies.md) - Custom ontology guide
- [ADRs](adrs/README.md) - Architectural decisions

## Contributing

When adding new library modules:

1. Add comprehensive docstrings (Google style)
2. Include type hints for all public functions
3. Write unit tests in `tests/unit/test_<module>.py`
4. Update `lib/__init__.py` with exports
5. Document in this reference guide
6. Add examples to README or ADR

## License

MIT - Same as mnemonic project
