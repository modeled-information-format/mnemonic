---
name: list
allowed-tools:
- Bash
- Read
- Glob
- Grep
- Write
description: List loaded ontologies and their namespaces
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# List Ontologies

Lists all loaded ontologies with their namespaces and entity types.

## Usage

```
/mnemonic:list [--namespaces] [--types] [--json]
```

## Options

- `--namespaces` - Show only namespaces
- `--types` - Show only entity types
- `--json` - Output as JSON

## Procedure

```bash
# Find and run the ontology registry from the plugin directory
PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-$(dirname $(dirname $0))}"
python3 "$PLUGIN_DIR/skills/ontology/lib/ontology_registry.py" ${ARGS}
```

**Flag mapping:**
- `/mnemonic:list` → `python3 ... --list`
- `/mnemonic:list --namespaces` → `python3 ... --namespaces`
- `/mnemonic:list --types` → `python3 ... --types`
- `/mnemonic:list --json` → `python3 ... --json`

If the Python script is not available, use the Read tool to display ontology files:

```bash
# Read base ontology
cat "${PLUGIN_DIR}/skills/ontology/fallback/ontologies/mif-base.ontology.yaml" 2>/dev/null

# Read project ontologies (MIF 1.4.2 location, then legacy)
cat .mif/ontologies/*.yaml 2>/dev/null
cat ".claude/mnemonic/ontology.yaml" 2>/dev/null

# Read user ontologies (MIF 1.4.2 location, then legacy)
cat "$HOME"/.mif/ontologies/*.yaml 2>/dev/null
cat "$HOME/.claude/mnemonic/ontology.yaml" 2>/dev/null
```

## Example Output

```
Loaded ontologies:
  - mif-base v1.0.0
    Namespaces: semantic/, _semantic/decisions, _semantic/knowledge, _semantic/entities,
                episodic/, _episodic/incidents, _episodic/sessions, _episodic/blockers,
                procedural/, _procedural/runbooks, _procedural/patterns, _procedural/migrations
    Traits: timestamped, confidence, provenance
    Relationships: relates-to, supersedes, derived-from

  - software-engineering v1.0.0 (extends mif-base)
    Entity types: component, architectural-decision, incident-report, technology
```
