---
allowed-tools:
- Bash
- Read
- Glob
- Grep
- Write
description: Validate an ontology YAML file against the meta-schema
name: validate
---
<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# Validate Ontology

Validates an ontology definition file for correctness.

## Usage

```
/mnemonic:validate <file> [--json]
```

## Arguments

- `<file>` - Path to ontology YAML file. Defaults to the first that exists of: `.mif/ontologies/ontology.yaml` or `.mif/ontologies/*.ontology.yaml` (project, MIF 1.4.2), `~/.mif/ontologies/ontology.yaml` or `~/.mif/ontologies/*.ontology.yaml` (user, MIF 1.4.2), then the legacy `$MNEMONIC_ROOT/ontology.yaml`
- `--json` - Output as JSON

## Checks Performed

- Required fields present (id, version)
- ID format (lowercase, hyphens)
- Version follows semver
- Valid base types (semantic, episodic, procedural)
- Traits defined before use
- Relationships reference valid entity types
- Discovery patterns are valid regex

## Procedure

```bash
# Resolve MNEMONIC_ROOT from config
if [ -f "$HOME/.config/mnemonic/config.json" ]; then
    RAW_PATH=$(python3 -c "import json; print(json.load(open('$HOME/.config/mnemonic/config.json')).get('memory_store_path', '~/.claude/mnemonic'))")
    MNEMONIC_ROOT="${RAW_PATH/#\~/$HOME}"
else
    MNEMONIC_ROOT="$HOME/.claude/mnemonic"
fi
# MIF 1.4.2 locations first (spec 10.8.5), legacy mnemonic location as fallback
if [ -n "$1" ]; then
    ONTOLOGY_FILE="$1"
else
    ONTOLOGY_FILE="$MNEMONIC_ROOT/ontology.yaml"
    for candidate in .mif/ontologies/ontology.yaml .mif/ontologies/*.ontology.yaml \
                     "$HOME/.mif/ontologies/ontology.yaml" "$HOME"/.mif/ontologies/*.ontology.yaml; do
        if [ -f "$candidate" ]; then ONTOLOGY_FILE="$candidate"; break; fi
    done
fi
PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT:-$(dirname $(dirname $0))}"

python3 "$PLUGIN_DIR/skills/ontology/lib/ontology_validator.py" "$ONTOLOGY_FILE" ${ARGS}
```

If Python validation unavailable, perform basic YAML checks:

```bash
# Check file exists
if [ ! -f "$ONTOLOGY_FILE" ]; then
    echo "Error: File not found: $ONTOLOGY_FILE"
    exit 1
fi

# Check required fields
if ! grep -q "^ontology:" "$ONTOLOGY_FILE"; then
    echo "Error: Missing 'ontology:' section"
    exit 1
fi

if ! grep -q "id:" "$ONTOLOGY_FILE"; then
    echo "Error: Missing 'id' field"
    exit 1
fi

echo "Basic validation passed for: $ONTOLOGY_FILE"
```

## Example Output

```
Validating: my-ontology.yaml
Status: VALID

Warnings (1):
  - [WARNING] traits.cited: Trait has no fields or requires defined
```
