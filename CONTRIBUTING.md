# Contributing to Mnemonic

Thank you for your interest in contributing to Mnemonic! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Development Setup

### Prerequisites

- Claude Code CLI
- Git
- Python 3.8+ (for hooks)
- ripgrep (recommended for search operations)

### Setup

```bash
# Clone the repository
git clone https://github.com/modeled-information-format/mnemonic.git
cd mnemonic

# Set up development environment
make setup

# Validate the plugin
make lint

# Run tests
make test
```

## Project Structure

```
mnemonic/
├── .claude-plugin/      # Plugin manifest
├── agents/              # Agent definitions
├── commands/            # Slash commands
├── docs/                # Documentation
│   ├── adrs/            # Architecture Decision Records
│   └── integrations/    # Multi-tool integration guides
├── hooks/               # Python hook implementations
├── skills/              # Self-contained skills
├── templates/           # Integration templates
├── tools/               # Utility scripts (validation, etc.)
└── tests/               # Tests and fixtures
```

## Making Changes

### Commands and Skills

Commands and skills are markdown files with YAML frontmatter:

```markdown
---
description: Brief description
argument-hint: "<args>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# Command/Skill Name

Full documentation...
```

### Hooks

Hooks are Python scripts in `hooks/`:

1. Must output valid JSON
2. Must handle errors gracefully
3. Must respect timeouts
4. Should be idempotent

```python
#!/usr/bin/env python3
import json
import sys

def main():
    result = {"continue": True}
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Code Style

### Python

- Follow PEP 8
- Use type hints where practical
- Run `make format` before committing
- Ensure `make lint` passes

### Markdown

- Use ATX-style headers (`#`)
- Code blocks must have language tags
- Tables should be properly aligned
- Maximum line length: 120 characters

## Testing

```bash
# Run all tests
make test

# Validate plugin structure
make lint

# Check formatting
make format-check

# Validate memory files
make validate-memories

# Validate memory files (JSON output for CI)
make validate-memories-ci
```

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch from `main`
   ```bash
   git checkout -b feature/my-feature
   ```
3. **Make** your changes with tests
4. **Format** and lint
   ```bash
   make format
   make lint
   ```
5. **Commit** with conventional commit messages
6. **Push** to your fork
7. **Open** a Pull Request

### PR Checklist

- [ ] Plugin validates (`make lint`)
- [ ] Commands/skills have proper frontmatter
- [ ] Python code passes linting
- [ ] Memory files validate (`make validate-memories`)
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated for user-facing changes
- [ ] No breaking changes (or clearly documented)

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add memory export command
fix: correct namespace path in recall
docs: update architecture diagram
test: add hook unit tests
refactor: simplify capture workflow
chore: update dependencies
```

## Documentation

- Update README.md for user-facing changes
- Update docs/architecture.md for structural changes
- Add ADRs for significant architectural decisions
- Include examples in command/skill definitions

## Memory Format

All memories must follow MIF Level 3 specification:

```yaml
---
id: UUID
type: semantic|episodic|procedural
namespace: category/scope
created: ISO-8601
modified: ISO-8601
title: "Title"
tags: []
temporal:
  valid_from: ISO-8601
  recorded_at: ISO-8601
provenance:
  source_type: conversation|user_explicit|inferred
  agent: model-identifier
  confidence: 0.0-1.0
---
```

## Questions?

Open an issue for discussion or clarification.
