# Memory Validation

The `mnemonic-validate` tool validates memory files against the MIF Level 3 schema.

## Quick Start

```bash
# Validate all memories (default paths)
./tools/mnemonic-validate

# Validate specific directory
./tools/mnemonic-validate ${MNEMONIC_ROOT}

# JSON output for CI/CD
./tools/mnemonic-validate --format json

# Using make targets
make validate-memories
make validate-memories-ci
```

## Installation

The validation tool is included with the mnemonic plugin. No additional installation required.

**Dependencies:** Python 3.9+ with PyYAML (included in most Python installations).

## Usage

```bash
mnemonic-validate [options] [path...]

Options:
  --format json|markdown   Output format (default: markdown)
  --check TYPE            Only validate: code_refs|citations|links|schema
  --skip-http             Skip HTTP checks (offline mode)
  --fast-fail             Stop on first error
  --changed               Only validate git-modified files
  --capture               Capture validation run as episodic memory
  -v, --verbose           Verbose output
  -h, --help              Show this help
```

### Default Paths

If no path is specified, the tool searches:
1. `${MNEMONIC_ROOT}/` (global memories)
2. `${MNEMONIC_ROOT}/` (project memories)

## Validation Checks

### Schema Validation (--check schema)

Validates MIF Level 3 required fields and formats:

| Field | Validation |
|-------|------------|
| `id` | Must be valid UUID v4 format (lowercase) |
| `type` | Must be `semantic`, `episodic`, or `procedural` |
| `namespace` | Should follow pattern `{namespace}/{scope}` |
| `created` | Must be valid ISO 8601 timestamp |
| `title` | Must be non-empty string |

Additional checks:
- `provenance.confidence` should be between 0.0 and 1.0
- `provenance.sourceType` should be a MIF 1.4.1 value (`user_explicit`,
  `user_implicit`, `agent_inferred`, `external_import`, `system_generated`)
- `compressedAt`, if present, must be an ISO 8601 timestamp
- `tags` should be lowercase with hyphens
- `temporal.validFrom` should be before or equal to `temporal.recordedAt`

### Legacy forms (warnings only)

Memories written by earlier mnemonic releases are still valid. These forms
produce **warnings**, never errors, each naming the MIF 1.4.1 replacement:

- snake_case frontmatter keys (`valid_from`, `source_type`, `compressed_at`,
  `code_refs`, ...)
- legacy `sourceType` values (`inferred`, `conversation`)
- relationship types not in kebab-case (`relates_to`, `RelatesTo`)
- relationship `label` outside `metadata`
- frontmatter relationships with no body `## Relationships` link
- `[[uuid]]` wiki-link relationship lines
- citations using `type` instead of `citationType`, or missing `citationRole`

`tools/mnemonic-migrate-mif` rewrites these in place on request (dry run by
default).

### Code References Validation (--check code_refs)

For memories with `codeRefs` (legacy: `code_refs`):
- `type` should be one of: `function`, `class`, `method`, `variable`, `type`, `module`
- `file` path should exist (relative to git root)
- `line` number should be within file length

### Citations Validation (--check citations)

For memories with `citations`:
- `citationType` (required; legacy spelling `type` accepted) should be a MIF
  1.4.1 value (`article`, `book`, `paper`, `website`, `documentation`,
  `repository`, `video`, `podcast`, `specification`, `dataset`, `tool`,
  `other`) or a legacy mnemonic value (`blog`, `github`, `stackoverflow`)
- `citationRole` should be present (warning if missing)
- `title` (required) must be non-empty
- `url` (required) must be valid URL format
- `relevance` (optional) should be between 0.0 and 1.0

### Memory Links Validation (--check links)

Validates relationship links:
- every frontmatter `relationships` entry should be mirrored as a Markdown
  link under `## Relationships` (MIF 1.4.1 section 5.3); a legacy
  `[[uuid]]` line counts as a mirror but is itself warned about
- legacy `[[uuid]]` patterns in the body must have a valid UUID format
- (Future: referenced memory should exist)

## Output Formats

### Markdown (default)

```markdown
# Mnemonic Validation Report

**Date:** 2026-01-24T10:30:00Z

## Summary

- **Memories validated:** 145
- **Valid:** 142
- **Errors:** 3
- **Warnings:** 5

## Errors

### abc123-example.memory.md

- **type**: Missing required field: type
- **id** (line 2): Invalid UUID format: not-a-uuid

## Warnings

### def456-other.memory.md

- **tags**: Tag should be lowercase with hyphens: CamelCase
```

### JSON (--format json)

```json
{
  "timestamp": "2026-01-24T10:30:00Z",
  "summary": {
    "total": 145,
    "valid": 142,
    "errors": 3,
    "warnings": 5
  },
  "results": [
    {
      "file": "abc123-example.memory.md",
      "valid": false,
      "errors": [
        {
          "file": "abc123-example.memory.md",
          "field": "type",
          "message": "Missing required field: type",
          "line": null,
          "severity": "error"
        }
      ],
      "warnings": []
    }
  ]
}
```

## CI/CD Integration

### Exit Codes

- `0`: All validations passed
- `1`: One or more errors found

### GitHub Actions Example

```yaml
name: Validate Memories

on:
  push:
    paths:
      - '**/*.memory.md'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Validate memories
        run: ./tools/mnemonic-validate --format json

      - name: Validate changed only
        if: github.event_name == 'pull_request'
        run: ./tools/mnemonic-validate --changed --format json
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: validate-memories
        name: Validate memory files
        entry: ./tools/mnemonic-validate --changed --fast-fail
        language: python
        types: [markdown]
        files: \.memory\.md$
```

## Capturing Validation Runs

Use `--capture` to save validation results as an episodic memory:

```bash
./tools/mnemonic-validate --capture
```

This creates a memory in:
- `blockers/project` if errors were found
- `episodic/project` if validation passed

The captured memory includes:
- Summary statistics
- List of errors and warnings
- Timestamp and provenance

This enables tracking validation history over time via mnemonic search.

## Makefile Targets

```bash
# Validate with markdown output
make validate-memories

# Validate with JSON output (for CI)
make validate-memories-ci

# Validate only changed files
make validate-memories-changed
```

## Troubleshooting

### "Cannot find MIF schema"

Ensure you're running from the mnemonic plugin directory or have set up paths correctly.

### "No memory files found"

Check that:
1. Memory files end with `.memory.md`
2. The search paths contain memory files
3. For `--changed`, files are tracked by git

### YAML Parse Errors

If frontmatter fails to parse:
- Check for invalid YAML syntax
- Ensure the file starts with `---`
- Verify closing `---` exists

## Schema Source

The validation rules are parsed from `skills/format/SKILL.md`, ensuring a single source of truth between documentation and validation (see ADR-004).
