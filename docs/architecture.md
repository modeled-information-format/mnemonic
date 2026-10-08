# Mnemonic Architecture

## Overview

Mnemonic is a pure filesystem-based memory system for Claude Code. It provides persistent knowledge storage across sessions using markdown files with YAML frontmatter.

## Design Principles

1. **No External Dependencies**: All operations use standard Unix tools (git, rg, find) and Claude's native capabilities
2. **Skill-First Architecture**: Skills are self-contained and work without hooks or libraries
3. **MIF Level 3 Compliance**: Modeled Information Format (MIF) 1.4.2 for interoperability; legacy pre-1.4.1 memories remain readable
4. **Filesystem as Database**: Markdown files are the source of truth

### Academic Foundations

These principles are grounded in both empirical research and theoretical foundations:

- **Research Validation**: [Letta's LoCoMo benchmark](https://www.letta.com/blog/benchmarking-ai-agent-memory) demonstrates that filesystem-based memory approaches achieve 74.0% accuracy compared to Mem0's graph-based approach at 68.5%. The key insight: LLMs are pretrained on filesystem operations, making simple tools more reliable than specialized abstractions.

- **Unix Philosophy**: The paper ["From Everything is a File to Files Are All You Need"](https://arxiv.org/abs/2601.11672) (arXiv:2601.11672) explicitly validates applying Unix's uniform file abstraction to agentic AI design. Agents interacting with REST APIs, SQL databases, vector stores, and file systems benefit from file-like abstractions where complexity is encapsulated.

- **Cognitive Memory Types**: The semantic, episodic, and procedural memory classification derives from cognitive science and is being directly adopted by AI agent frameworks. See ["Human-inspired Perspectives: A Survey on AI Long-term Memory"](https://arxiv.org/abs/2411.00489) for theoretical grounding.

- **Bi-Temporal Modeling**: The valid_time vs recorded_at distinction follows the [SQL:2011 standard for temporal databases](https://en.wikipedia.org/wiki/Temporal_database#SQL:2011) and [Martin Fowler's bitemporal patterns](https://martinfowler.com/articles/bitemporal-history.html).

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                        │
├─────────────────────────────────────────────────────────────┤
│  Plugin Layer                                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │Commands │  │ Skills  │  │ Agents  │  │  Hooks  │         │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘         │
│       │            │            │            │              │
│       └────────────┴────────────┴────────────┘              │
│                         │                                   │
├─────────────────────────┼───────────────────────────────────┤
│  Storage Layer          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Filesystem (.memory.md files)           │   │
│  │  ┌─────────────────┐    ┌─────────────────────────┐  │   │
│  │  │  User-Level     │    │  Project-Level          │  │   │
│  │  │  ~/.claude/     │    │     │  │   │
│  │  │  mnemonic/{org}/│    │                         │  │   │
│  │  └─────────────────┘    └─────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────┴───────────────────────────────┐   │
│  │                    Git Repository                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Commands

Simple slash commands for direct user interaction:

| Command | Purpose |
|---------|---------|
| `/mnemonic:setup` | Initialize and configure mnemonic |
| `/mnemonic:capture` | Create a new memory |
| `/mnemonic:recall` | Retrieve memories |
| `/mnemonic:search` | Full-text search and iterative synthesis |
| `/mnemonic:status` | System status |
| `/mnemonic:gc` | Garbage collection |

### Skills

Self-contained instruction sets that work without external dependencies:

- **core**: Complete memory operations
- **setup**: CLAUDE.md configuration
- **search**: Advanced search patterns and iterative synthesis
- **format**: MIF Level 3 templates and schema
- **blackboard**: Cross-session coordination and agent patterns
- **ontology**: Custom ontology support with entity types and discovery
- **custodian**: Memory health checks and maintenance
- **integrate**: Plugin integration via sentinel markers
- **qmd-setup**: Semantic search bootstrap
- **qmd-reindex**: Memory re-indexing for semantic search

### Hooks

Event-driven context injection via `hookSpecificOutput.additionalContext`:

```
SessionStart ──────► Memory status, health score, registry status
                     Blackboard pending items

PreToolUse ────────► Relevant memory paths when editing files
                     File pattern detection (auth, api, db, test, etc.)

UserPromptSubmit ──► Capture/recall trigger detection
                     Topic extraction for search

PostToolUse ───────► Capture opportunity context
                     Error/success detection

Stop ──────────────► Commit pending changes
                     Session summary
```

**Key Principle**: Hooks provide context, Claude decides. Hooks do not instruct Claude to take specific actions—they inform Claude about available memories and detected patterns, and Claude autonomously decides whether to read memories or use agents.

### Agents

Autonomous background operations:

- **memory-curator**: Conflict detection, deduplication, decay management
- **mnemonic-search-subcall**: Efficient search agent for iterative query refinement (Haiku model)
- **compression-worker**: Memory summarization for gc --compress (Haiku model)

Agents coordinate through the blackboard pattern. See the [blackboard skill](../skills/blackboard/SKILL.md) for details.

### Tools

Validation and maintenance utilities:

- **mnemonic-validate**: Validates memories against MIF Level 3 schema. See [Validation](validation.md).

## Memory Model

### MIF Level 3 Format

```yaml
---
id: UUID
type: semantic|episodic|procedural
namespace: category/scope
created: ISO-8601
modified: ISO-8601
title: "Human readable title"
tags: [list, of, tags]
temporal:
  validFrom: ISO-8601
  recordedAt: ISO-8601
  decay:
    model: exponential
    halfLife: P7D
    strength: 0.0-1.0
provenance:
  sourceType: user_explicit | user_implicit | agent_inferred | external_import | system_generated
  agent: model-identifier
  confidence: 0.0-1.0
citations:                        # Optional external references
  - type: documentation|paper|blog|github|stackoverflow|article
    title: "Source Title"
    url: https://example.com
    relevance: 0.0-1.0
---

# Markdown Content

Body of the memory...
```

### Memory Types

| Type | Description | Decay Rate |
|------|-------------|------------|
| **semantic** | Facts, concepts, specifications | Slow (P30D) |
| **episodic** | Events, experiences, incidents | Fast (P7D) |
| **procedural** | Processes, workflows, how-tos | Medium (P14D) |

### Namespace Hierarchy

```
{root}/
├── apis/           # API documentation
├── blockers/       # Issues, impediments
├── context/        # Background information
├── decisions/      # Architectural choices
├── learnings/      # Insights, discoveries
├── patterns/       # Code conventions
├── security/       # Security policies
├── testing/        # Test strategies
├── episodic/       # General events
└── .blackboard/    # Cross-session coordination
```

## Data Flow

### Capture Flow

```
User/Claude identifies capturable content
           │
           ▼
    ┌──────────────┐
    │ Generate UUID │
    │ Set timestamps│
    │ Classify type │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Write .memory│
    │ .md file     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Git add +    │
    │ commit       │
    └──────────────┘
```

### Recall Flow

```
User query or topic detection
           │
           ▼
    ┌──────────────┐
    │ ripgrep      │
    │ search       │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Parse matches│
    │ Extract meta │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Rank by      │
    │ relevance    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Update access│
    │ timestamps   │
    └──────────────┘
```

## Cross-Session Coordination

The blackboard provides a shared space for session handoffs:

```
Session A                    Session B
    │                            │
    ├── Write to blackboard ─────┤
    │   (active-tasks.md)        │
    │                            │
    └── Stop hook commits ───────┼── SessionStart reads
                                 │   blackboard
                                 │
                                 └── Continues work
```

## Git Integration

All memories are version-controlled:

- **Atomic commits**: Each capture creates a commit
- **History tracking**: Full audit trail of changes
- **Branching**: Support for experimental memories
- **Conflict resolution**: Git merge for concurrent sessions

## Memory Maintenance

### Garbage Collection

The `/mnemonic:gc` command manages memory lifecycle:

- **Age-based cleanup**: Archive memories older than threshold
- **TTL expiry**: Remove memories past their time-to-live
- **Decay-based cleanup**: Archive low-strength memories
- **Compression**: Summarize verbose older memories (via `--compress`)

### Compression

Large memories can be compressed while preserving content:

```yaml
# Added by gc --compress
summary: "Concise summary (max 500 chars)"
compressedAt: 2026-01-24T10:00:00Z
```

Compression criteria:
- Age > 30 days AND lines > 100, OR
- Strength < 0.3 AND lines > 100

### Validation

The `mnemonic-validate` tool checks MIF Level 3 compliance:

```bash
# Validate all memories
./tools/mnemonic-validate

# CI-friendly JSON output
./tools/mnemonic-validate --format json
```

See [Validation](validation.md) for details.

## Multi-Agent Coordination

Agents coordinate using the blackboard pattern (ADR-003):

```
┌─────────────────────────────────────────────────────────────┐
│                       Blackboard                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │session-notes │  │active-tasks  │  │shared-context│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         ▼                 ▼                 ▼               │
│      Register          Handoff          Workflow            │
│      Status            Context          State               │
└─────────────────────────────────────────────────────────────┘
         ▲                 ▲                 ▲
         │                 │                 │
┌────────┴─────┐  ┌────────┴─────┐  ┌────────┴─────┐
│memory-curator│  │search-subcall│  │compress-worker│
└──────────────┘  └──────────────┘  └───────────────┘
```

See the [blackboard skill](../skills/blackboard/SKILL.md) for patterns.

## Performance Considerations

- **Search**: ripgrep provides fast full-text search
- **Indexing**: Filesystem is the index (no separate DB)
- **Caching**: Recent memories cached in context
- **Decay**: Exponential decay reduces noise over time
- **Compression**: Reduces storage for older memories
- **Agent isolation**: Subcall agents run in separate context (haiku model)

## Related Documentation

- [Validation](validation.md) - MIF schema validation
- [ADRs](adrs/README.md) - Architectural decisions
