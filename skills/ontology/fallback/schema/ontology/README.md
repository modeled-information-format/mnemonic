# MIF Ontology Schema

This directory contains the schema definitions for MIF (Modeled Information
Format) ontology files, vendored from the **MIF 1.4.1** release
(`public/schema/1.4.1/ontology/` in the
[MIF repository](https://github.com/modeled-information-format/MIF), release
commit `dd5e99e7`). The canonical, always-current copy is
<https://mif-spec.dev/schema/ontology/ontology.schema.json>; this copy exists
so offline installations can still validate ontologies.

Do not hand-edit these files. To update, copy both files verbatim from the
matching MIF release's `public/schema/<version>/ontology/` directory and add
an entry to `CHANGELOG.md`.

## Files

### ontology.schema.json

JSON Schema (draft 2020-12) for validating ontology YAML files. Key features:

- **Hierarchical namespaces**: Supports cognitive triad hierarchy (semantic/episodic/procedural) with nested children
- **Entity types**: Custom entity definitions with traits and JSON Schema validation
- **Discovery patterns**: Content and file pattern matching for entity suggestions
- **Relationships**: Typed relationships between entities

### ontology.context.jsonld

JSON-LD context for semantic web compatibility. Maps ontology concepts to:

- **Schema.org** for common properties (name, description, version)
- **SKOS** for concept hierarchies
- **OWL** for relationship semantics
- **Custom MIF vocabulary** for memory-specific concepts

## Usage

### Validating an ontology file

```bash
# Using ajv-cli
npx ajv validate -s ontology.schema.json -d ../../ontologies/mif-base.ontology.yaml

# Using Python jsonschema
python -c "
import json, yaml
from jsonschema import validate

with open('ontology.schema.json') as f:
    schema = json.load(f)
with open('../../ontologies/mif-base.ontology.yaml') as f:
    data = yaml.safe_load(f)
validate(data, schema)
print('Valid!')
"
```

### Converting to JSON-LD

```bash
python ../../scripts/yaml2jsonld.py ../../ontologies/mif-base.ontology.yaml
```

## Schema Evolution

- **MIF 1.4.1** (current): vendored verbatim from the MIF 1.4.1 release
- Earlier copies (`v1`, `v2` in `CHANGELOG.md`) were mnemonic-local edits
  that matched no MIF release

The schema `$id` is unversioned and stable by design (MIF ADR-007); the MIF
release a vendored copy came from is recorded here and in `CHANGELOG.md`.
