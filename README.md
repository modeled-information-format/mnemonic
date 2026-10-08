# Mnemonic

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blueviolet)](https://docs.anthropic.com/en/docs/claude-code)
[![MIF Level 3](https://img.shields.io/badge/MIF-Level%203-green)](https://mif-spec.dev)
[![Filesystem Approach](https://img.shields.io/badge/Filesystem-Research%20Validated-brightgreen)](https://www.letta.com/blog/benchmarking-ai-agent-memory)

A pure filesystem-based memory system for Claude Code. No external dependencies - all operations use standard Unix tools and Claude's native capabilities.

<p align="center">
  <img src=".github/readme-infographic.png" alt="Mnemonic Architecture" width="800">
</p>

> **Note**: This plugin implements the [Modeled Information Format (MIF)](https://mif-spec.dev) specification, version 1.4.1, as an AI-memory store (the use case MIF's AI Memory profile describes). MIF defines a portable, human-readable Markdown-plus-YAML format for knowledge.

## Features

- **Pure Filesystem**: All memories stored as markdown files with YAML frontmatter
- **MIF 1.4.1 Level 3**: New memories are written in Modeled Information Format 1.4.1 form; memories written by earlier releases keep working (see [MIF 1.4.1 alignment](#mif-141-alignment))
- **Skill-First Architecture**: Skills work standalone without hooks or libraries
- **Cognitive Memory Types**: Semantic, episodic, and procedural memories
- **Custom Ontologies**: Extend with domain-specific entity types and relationships
- **Semantic Search**: Optional vector search via qmd integration
- **Bi-Temporal Tracking**: Valid time vs. recorded time
- **Git Versioned**: All changes tracked with git
- **Cross-Session Coordination**: Blackboard for session handoffs

## Why Filesystem?

Research validates the filesystem approach for AI memory. In [Letta's LoCoMo benchmark](https://www.letta.com/blog/benchmarking-ai-agent-memory), filesystem-based memory achieved **74.0% accuracy** compared to Mem0's graph-based approach at **68.5%**. This counterintuitive result has a simple explanation: LLMs are extensively pretrained on filesystem operations, making simple tools more reliable than specialized knowledge graphs or vector databases.

This approach is grounded in Unix philosophy, as articulated in ["From Everything is a File to Files Are All You Need"](https://arxiv.org/abs/2601.11672). Just as Unix collapsed diverse device interfaces into uniform file operations, AI agents benefit from the same abstraction—complexity is encapsulated, not eliminated.

**Key advantages of the filesystem approach:**
- LLMs already understand `grep`, `find`, and file operations from training data
- Human-readable format enables direct inspection and editing
- Git integration provides full version history with meaningful diffs
- No external services, databases, or cloud dependencies
- Works offline and respects data sovereignty

## Installation

```bash
# Load the plugin
claude --plugin-dir /path/to/mnemonic

# Or add to settings for permanent installation
claude settings plugins add /path/to/mnemonic
```

## Quick Start

```bash
# Initialize mnemonic for your project
/mnemonic:setup

# Capture a memory
/mnemonic:capture decisions "Use PostgreSQL for storage" --tags database,architecture

# Recall memories
/mnemonic:recall --namespace decisions

# Search memories
/mnemonic:search "authentication"

# Check status
/mnemonic:status
```

## Directory Structure

All memories are stored under `${MNEMONIC_ROOT}/` with a unified path structure:

```
${MNEMONIC_ROOT}/
├── default/                           # Fallback when org detection fails
│   └── {namespace}/                   # Cognitive triad namespaces
├── {org}/                             # Organization-level
│   ├── semantic/                      # Org-wide facts/knowledge
│   │   ├── decisions/
│   │   ├── knowledge/
│   │   └── entities/
│   ├── episodic/                      # Org-wide events
│   │   ├── incidents/
│   │   ├── sessions/
│   │   └── blockers/
│   ├── procedural/                    # Org-wide procedures
│   │   ├── runbooks/
│   │   ├── patterns/
│   │   └── migrations/
│   └── {project}/                     # Project-specific memories
│       ├── semantic/
│       │   ├── decisions/
│       │   ├── knowledge/
│       │   └── entities/
│       ├── episodic/
│       │   ├── incidents/
│       │   ├── sessions/
│       │   └── blockers/
│       ├── procedural/
│       │   ├── runbooks/
│       │   ├── patterns/
│       │   └── migrations/
│       └── .blackboard/               # Project session coordination
└── .git/                              # Version control
```

**Memory scope hierarchy:**
- `{org}/{project}/` - Project-specific memories (default)
- `{org}/` - Organization-wide memories (shared across projects)
- `default/` - Fallback when org cannot be detected

## Memory Format (MIF Level 3)

Each memory is a `.memory.md` file with YAML frontmatter:

```yaml
---
id: 550e8400-e29b-41d4-a716-446655440000
type: semantic
namespace: decisions/project
created: 2026-01-23T10:30:00Z
modified: 2026-01-23T14:22:00Z
title: "Use PostgreSQL for storage"
tags:
  - database
  - architecture
temporal:
  validFrom: 2026-01-23T00:00:00Z
  recordedAt: 2026-01-23T10:30:00Z
  decay:
    model: exponential
    halfLife: P7D
    strength: 0.85
provenance:
  sourceType: user_explicit
  agent: claude-opus-4
  confidence: 0.95
relationships:
  - type: relates-to
    target: urn:mif:a5e46807-6883-4fb2-be45-09872ae1a994
    metadata:
      label: "Related caching decision"
  - type: supersedes
    target: urn:mif:b6f57918-7994-4dc3-af56-10983bf2b005
---

# Use PostgreSQL for Storage

We decided to use PostgreSQL for our data storage needs.

## Rationale
- Strong ACID compliance
- Excellent JSON support
- Mature ecosystem

## Relationships

- relates-to [Use Redis for caching](urn:mif:a5e46807-6883-4fb2-be45-09872ae1a994)
- supersedes [Use SQLite for storage](urn:mif:b6f57918-7994-4dc3-af56-10983bf2b005)
```

### MIF 1.4.1 alignment

New memories use the MIF 1.4.1 forms shown above: camelCase frontmatter keys
(`validFrom`, `sourceType`, `compressedAt`, ...), kebab-case relationship
types (`relates-to`), `urn:mif:<uuid>` relationship targets, and every
frontmatter relationship mirrored as a Markdown link under `## Relationships`.

Memories written by earlier mnemonic releases are **still read as-is**:
snake_case keys (`valid_from`, `compressed_at`), `relates_to`/`RelatesTo`
types, bare-UUID targets, and `[[uuid]]` wiki-links all resolve to the same
values. `make validate-memories` reports them as warnings, never errors.

To upgrade old files in place, use the opt-in migration tool. It only
previews unless you pass `--apply`, and writes a `.pre-mif-1.4.1.bak` copy of
every file it changes:

```bash
tools/mnemonic-migrate-mif                 # dry run over all memory roots
tools/mnemonic-migrate-mif path/to/dir     # dry run over one directory
tools/mnemonic-migrate-mif --apply         # rewrite in place (with backups)
```

Memory files keep the `{slug}.memory.md` name. MIF 1.4.1 calls the `.memory`
infix legacy, but every mnemonic search, hook and tool globs `*.memory.md`, so
renaming is out of scope for this tool.

Custom ontologies are resolved from MIF's locations first (project
`.mif/ontologies/`, then user `~/.mif/ontologies/`, both `*.ontology.yaml`),
falling back to the earlier `.claude/mnemonic/ontology.yaml` and
`${MNEMONIC_ROOT}/.../ontology.yaml` locations.

## Memory Types

| Type | Use Case | Examples |
|------|----------|----------|
| **semantic** | Facts, concepts, specifications | API docs, config values |
| **episodic** | Events, experiences, incidents | Debug sessions, deployments |
| **procedural** | Processes, workflows, how-tos | Deployment steps, runbooks |

## Namespaces

Mnemonic uses a cognitive triad namespace hierarchy:

| Top-Level | Sub-namespace | Purpose |
|-----------|---------------|---------|
| `semantic/` | `decisions/` | Architectural choices, rationale |
| | `knowledge/` | APIs, context, learnings, security |
| | `entities/` | Entity definitions (technologies, components) |
| `episodic/` | `incidents/` | Production issues, postmortems |
| | `sessions/` | Debug sessions, work sessions |
| | `blockers/` | Impediments, issues |
| `procedural/` | `runbooks/` | Operational procedures |
| | `patterns/` | Code conventions, testing strategies |
| | `migrations/` | Migration steps, upgrade procedures |

## Custom Ontologies

Extend mnemonic with domain-specific entity types, relationships, and discovery:

```bash
# Copy the software-engineering ontology into the project's MIF ontology dir
mkdir -p .mif/ontologies
cp skills/ontology/fallback/ontologies/examples/software-engineering.ontology.yaml \
   .mif/ontologies/
```

(`~/.mif/ontologies/` applies an ontology to every project. The older
`.claude/mnemonic/ontology.yaml` location is still read as a fallback.)

This adds:
- Custom sub-namespaces (architecture, components, deployments)
- Typed entities (technology, component, design-pattern, incident-report, runbook)
- Entity relationships (depends_on, implements, caused_by, resolves)
- Discovery patterns for auto-suggesting entity captures

See [docs/ontologies.md](docs/ontologies.md) for the full guide.

## Commands

| Command | Description |
|---------|-------------|
| `/mnemonic:setup` | Configure mnemonic with proactive behavior |
| `/mnemonic:capture` | Capture a new memory |
| `/mnemonic:recall` | Search and recall memories |
| `/mnemonic:search` | Full-text search and enhanced iterative search |
| `/mnemonic:query` | Structured frontmatter queries using yq |
| `/mnemonic:status` | Show system status |
| `/mnemonic:gc` | Garbage collect expired memories |
| `/mnemonic:list` | List loaded ontologies and namespaces |
| `/mnemonic:validate` | Validate ontology file |
| `/mnemonic:custodian` | Memory health checks and maintenance |
| `/mnemonic:integrate` | Wire mnemonic into other plugins |

## Skills

Skills are fully self-contained and work without hooks or libraries:

- **setup**: Configure CLAUDE.md for proactive behavior
- **core**: Complete memory operations
- **search**: Advanced search patterns and iterative synthesis
- **format**: MIF Level 3 templates
- **blackboard**: Cross-session coordination and agent patterns
- **ontology**: Custom ontology support with entity types and discovery
- **custodian**: Memory maintenance, deduplication, and health checks
- **integrate**: CLAUDE.md integration for new projects
- **qmd-setup**: Semantic search setup via qmd
- **qmd-reindex**: Re-index memories for semantic search

## Agents

Autonomous agents for specialized tasks:

- **memory-curator**: Conflict detection, deduplication, decay management
- **mnemonic-search-subcall**: Efficient search agent for iterative query refinement
- **compression-worker**: Memory summarization for gc --compress
- **ontology-discovery**: Discovers entities in codebase based on ontology patterns

## Documentation

| Guide | Focus |
|-------|-------|
| [Getting Started](docs/tutorials/getting-started.md) | First project setup tutorial |
| [CLI Usage](docs/cli-usage.md) | Command-line operations |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Architecture](docs/architecture.md) | System architecture |
| [Semantic Search](docs/semantic-search.md) | QMD vector search setup |
| [Library Reference](docs/library-reference.md) | Python library API reference |
| [Ontologies](docs/ontologies.md) | Custom ontology guide |
| [Validation](docs/validation.md) | Memory validation guide |
| [ADRs](docs/adrs/) | Architecture decision records |
| [Org governance & release runbooks](docs/reference/org-governance.md) | Org-wide release, branch-protection, Dependabot, and labels runbooks |

## Proactive Behavior

After running `/mnemonic:setup`, Claude will:

1. **Auto-Recall**: Silently search for relevant memories when you discuss topics
2. **Auto-Capture**: Automatically save decisions, learnings, and patterns
3. **Silent Operation**: Memory operations happen in the background

## Search

Mnemonic provides both traditional keyword search and semantic vector search.

### Keyword Search (ripgrep)

```bash
# Full-text search
rg -i "authentication" ${MNEMONIC_ROOT}/ --glob "*.memory.md"

# By namespace
rg "pattern" ${MNEMONIC_ROOT}/*/_semantic/decisions/ --glob "*.memory.md"

# By tag
rg -l "^  - security" ${MNEMONIC_ROOT}/ --glob "*.memory.md"

# By type
rg "^type: episodic" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l

# Recent files (last 7 days)
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime -7
```

### Semantic Search (qmd)

For semantic/vector search capabilities, use the integrated `@tobilu/qmd` support:

```bash
# One-time setup
/mnemonic:qmd-setup

# Keyword search (BM25)
qmd search "authentication patterns"

# Semantic vector search
qmd vsearch "how do we handle user sessions"

# Hybrid search (BM25 + vector)
qmd query "database migration strategy"

# Scope to specific collections
qmd search "auth" -c mnemonic-zircote    # org memories only
qmd search "auth" -c mnemonic-project    # this repo only

# Re-index after adding new memories
/mnemonic:qmd-reindex
```

**Requirements:**
- Node.js >= 22
- `npm i -g @tobilu/qmd`

See [skills/qmd-setup/SKILL.md](skills/qmd-setup/SKILL.md) for detailed setup instructions.

## Hooks

Hooks provide proactive automation via `hookSpecificOutput.additionalContext`:

| Event | Purpose |
|-------|---------|
| SessionStart | Memory status, health score, registry status |
| PreToolUse | Relevant memory paths when editing files |
| UserPromptSubmit | Capture/recall trigger detection |
| PostToolUse | Capture opportunities from tool results |
| Stop | Commit changes, summarize session |

Hooks inform Claude with context—Claude decides when to read memories or use agents.

## Blackboard

The blackboard enables cross-session coordination:

```bash
# Write to blackboard
echo "## Task started" >> ${MNEMONIC_ROOT}/.blackboard/active-tasks.md

# Read recent entries
tail -50 ${MNEMONIC_ROOT}/.blackboard/session-notes.md
```

## Git Versioning

All memories are versioned with git:

```bash
cd ${MNEMONIC_ROOT}
git log --oneline -20
git show HEAD~3:path/to/memory.memory.md
```

## Development

```bash
# Project structure
mnemonic/
├── .claude-plugin/
│   └── plugin.json         # Plugin manifest
├── agents/
│   ├── memory-curator.md           # Maintenance agent
│   ├── mnemonic-search-subcall.md  # Search iteration agent
│   ├── compression-worker.md       # Memory summarization agent
│   └── ontology-discovery.md       # Entity discovery agent
├── commands/
│   └── *.md                # Slash commands
├── docs/
│   ├── architecture.md     # System architecture
│   ├── semantic-search.md  # QMD semantic search guide
│   ├── validation.md       # Memory validation guide
│   ├── ontologies.md       # Custom ontology guide
│   ├── cli-usage.md        # Command-line operations
│   ├── library-reference.md # Python library API
│   ├── troubleshooting.md  # Common issues and solutions
│   └── adrs/               # Architecture decision records
├── hooks/
│   ├── hooks.json          # Hook configuration
│   └── *.py                # Hook implementations
├── lib/
│   ├── paths.py            # Path resolution
│   ├── config.py           # Configuration
│   ├── ontology.py         # Ontology loading
│   ├── search.py           # Memory search and scoring
│   ├── memory_reader.py    # Memory metadata extraction
│   ├── relationships.py    # Relationship writing
│   └── migrate_filenames.py # Filename migration utilities
├── skills/
│   ├── */SKILL.md          # Self-contained skills
│   └── ontology/           # Custom ontology support
│       ├── SKILL.md
│       ├── lib/            # Python utilities
│       └── ontologies/     # Base ontology and examples
├── tools/
│   ├── mnemonic-validate   # MIF schema validation
│   ├── mnemonic-migrate-mif # Opt-in legacy -> MIF 1.4.1 rewrite (dry run by default)
│   ├── mnemonic-query      # Structured queries
│   └── mnemonic-paths      # Path resolution CLI
├── tests/
│   └── unit/               # Unit tests
├── CHANGELOG.md
└── README.md
```

## Requirements

### Core Dependencies

- Claude Code CLI
- Git
- ripgrep (recommended for search)
- yq (required for structured queries)
- Python 3.8+ (for hooks and tools)

### Optional: Semantic Search

- Node.js >= 22
- `@tobilu/qmd` (`npm i -g @tobilu/qmd`)

### Installing Dependencies

```bash
# macOS
brew install ripgrep yq

# Ubuntu/Debian
apt install ripgrep
snap install yq

# Optional: semantic search
npm i -g @tobilu/qmd

# Check installation
make check-deps
```

## Related Projects

- **[MIF (Modeled Information Format)](https://mif-spec.dev)** - The specification this plugin implements (1.4.1). An open, OKF-compatible standard for portable knowledge; mnemonic uses its AI Memory profile. Schemas: https://mif-spec.dev/schema/

## License

MIT
