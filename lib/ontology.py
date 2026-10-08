#!/usr/bin/env python3
"""
Mnemonic Ontology Loading Library

Centralized ontology loading for all mnemonic hooks.
Consolidates duplicated ontology resolution logic from:
- hooks/pre_tool_use.py (file patterns)
- hooks/post_tool_use.py (ontology data, file patterns)
- hooks/user_prompt_submit.py (content patterns)
- hooks/session_start.py (namespaces, ontology info)
"""

from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from lib.mif_compat import merge_ontologies
from lib.paths import get_v2_resolver


def get_ontology_file() -> Optional[Path]:
    """Find the MIF base ontology file.

    Searches standard locations relative to the plugin root directory.

    Returns:
        Path to the ontology file, or None if not found.
    """
    plugin_root = Path(__file__).parent.parent
    ontology_paths = [
        plugin_root / "skills" / "ontology" / "fallback" / "ontologies" / "mif-base.ontology.yaml",
    ]

    for path in ontology_paths:
        if path.exists():
            return path

    return None


def _load_yaml_file(path: Path):
    """Load a YAML file, returning None if yaml is unavailable or on failure."""
    if not yaml:
        return None
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def load_ontology_data() -> dict:
    """Load full ontology data including relationships.

    Returns:
        Parsed ontology dict, or empty dict on failure.
    """
    ontology_file = get_ontology_file()
    if not ontology_file or not yaml:
        return {}

    data = _load_yaml_file(ontology_file)
    return data if data else {}


def load_file_patterns() -> list:
    """Load file patterns from MIF ontology discovery configuration.

    Returns:
        List of dicts with keys: patterns, namespaces, context.
    """
    ontology_file = get_ontology_file()
    if not ontology_file or not yaml:
        return get_fallback_file_patterns()

    try:
        with open(ontology_file) as f:
            data = yaml.safe_load(f)

        discovery = data.get("discovery", {})
        if not discovery.get("enabled", False):
            return get_fallback_file_patterns()

        patterns = []
        for fp in discovery.get("file_patterns", []):
            pattern = fp.get("pattern")
            namespaces = fp.get("namespaces", [])
            context = fp.get("context", "")
            if pattern and namespaces:
                patterns.append({"patterns": pattern.split("|"), "namespaces": namespaces, "context": context})

        return patterns if patterns else get_fallback_file_patterns()

    except Exception:
        return get_fallback_file_patterns()


def load_content_patterns() -> dict:
    """Load content patterns (capture trigger regexes) from MIF ontology.

    Returns:
        Dict mapping namespace -> list of regex patterns.
    """
    patterns = {}

    ontology_file = get_ontology_file()
    if not ontology_file or not yaml:
        return get_fallback_content_patterns()

    try:
        with open(ontology_file) as f:
            data = yaml.safe_load(f)

        discovery = data.get("discovery", {})
        if not discovery.get("enabled", False):
            return get_fallback_content_patterns()

        for cp in discovery.get("content_patterns", []):
            namespace = cp.get("namespace")
            pattern = cp.get("pattern")
            if namespace and pattern:
                if namespace not in patterns:
                    patterns[namespace] = []
                patterns[namespace].append(pattern)

        return patterns if patterns else get_fallback_content_patterns()

    except Exception:
        return get_fallback_content_patterns()


def load_ontology_namespaces() -> list:
    """Load all namespaces from MIF and custom ontology files.

    Returns:
        List of namespace path strings.
    """
    base_namespaces = [
        "_semantic",
        "_semantic/decisions",
        "_semantic/knowledge",
        "_semantic/entities",
        "_episodic",
        "_episodic/incidents",
        "_episodic/sessions",
        "_episodic/blockers",
        "_procedural",
        "_procedural/runbooks",
        "_procedural/patterns",
        "_procedural/migrations",
    ]

    custom_namespaces = []
    ontology_paths = get_v2_resolver().get_ontology_paths()

    if not yaml:
        return base_namespaces

    for ont_path in ontology_paths:
        if ont_path.exists():
            try:
                with open(ont_path) as f:
                    data = yaml.safe_load(f)
                if data and "namespaces" in data:
                    _collect_namespaces(data["namespaces"], "", custom_namespaces)
            except Exception:
                pass

    return list(set(base_namespaces + custom_namespaces))


def _collect_namespaces(namespaces: dict, prefix: str, result: list):
    """Recursively collect namespace paths from hierarchical structure."""
    for name, data in namespaces.items():
        path = f"{prefix}/{name}" if prefix else name
        result.append(path)
        if isinstance(data, dict) and "children" in data:
            _collect_namespaces(data["children"], path, result)


def _extract_entity_type_names(data: dict) -> list:
    """Extract entity type names from ontology data."""
    ets = data.get("entity_types", [])
    if isinstance(ets, list):
        return [et.get("name") for et in ets if isinstance(et, dict)]
    return []


def get_fallback_file_patterns() -> list:
    """Canonical fallback file patterns (8 categories).

    Used when ontology loading fails or discovery is disabled.
    """
    return [
        {
            "patterns": ["auth", "login", "session", "jwt", "oauth"],
            "namespaces": ["_semantic/knowledge", "_semantic/decisions"],
            "context": "authentication",
        },
        {
            "patterns": ["api", "endpoint", "route", "controller"],
            "namespaces": ["_semantic/knowledge", "_semantic/decisions"],
            "context": "API design",
        },
        {
            "patterns": ["db", "database", "model", "schema", "migration"],
            "namespaces": ["_semantic/decisions", "_procedural/migrations"],
            "context": "database",
        },
        {"patterns": ["test", "spec", "mock", "fixture"], "namespaces": ["_procedural/patterns"], "context": "testing"},
        {
            "patterns": ["config", "settings", "env"],
            "namespaces": ["_semantic/decisions", "_semantic/knowledge"],
            "context": "configuration",
        },
        {
            "patterns": ["deploy", "docker", "kubernetes", "helm"],
            "namespaces": ["_procedural/runbooks", "_semantic/decisions"],
            "context": "deployment",
        },
        {
            "patterns": ["security", "encrypt", "hash", "sanitize"],
            "namespaces": ["_semantic/knowledge", "_semantic/decisions"],
            "context": "security",
        },
        {
            "patterns": ["service", "component", "module"],
            "namespaces": ["_semantic/entities", "_semantic/decisions"],
            "context": "components",
        },
    ]


def get_fallback_content_patterns() -> dict:
    """Canonical fallback content patterns (capture trigger regexes).

    Used when ontology loading fails or discovery is disabled.
    """
    return {
        "_semantic/decisions": [
            r"\blet'?s use\b",
            r"\bwe'?ll use\b",
            r"\bdecided to\b",
            r"\bgoing with\b",
            r"\bdecision:\b",
            r"\bselected\b",
        ],
        "_semantic/knowledge": [
            r"\blearned that\b",
            r"\bturns out\b",
            r"\bthe fix was\b",
        ],
        "_procedural/patterns": [
            r"\bshould always\b",
            r"\balways use\b",
            r"\bconvention\b",
        ],
        "_episodic/blockers": [
            r"\bblocked by\b",
            r"\bstuck on\b",
        ],
        "_episodic/incidents": [
            r"\boutage\b",
            r"\bincident\b",
            r"\bpostmortem\b",
        ],
        "_procedural/runbooks": [
            r"\brunbook\b",
            r"\bplaybook\b",
            r"\bSOP\b",
        ],
    }


def validate_memory_against_ontology(
    namespace: str,
    memory_type: str,
    ontology_data: dict,
) -> list[str]:
    """Validate a memory's namespace and type against loaded ontology.

    Checks:
    1. Namespace is defined in the ontology's namespace hierarchy
    2. Memory type matches the namespace's expected cognitive type

    Args:
        namespace: Full namespace path (e.g., "_semantic/decisions")
        memory_type: Memory type (e.g., "semantic", "episodic", "procedural")
        ontology_data: Parsed ontology YAML dict (from load_ontology_data())

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []

    if not ontology_data:
        return errors  # No ontology loaded, skip validation

    # Collect all valid namespaces from ontology
    valid_namespaces: list[str] = []
    if "namespaces" in ontology_data:
        _collect_namespaces(ontology_data["namespaces"], "", valid_namespaces)

    # Validate namespace exists in ontology
    if valid_namespaces and namespace not in valid_namespaces:
        # Allow bare top-level namespaces (e.g., "_semantic") only if they are
        # explicitly defined; unknown sub-namespaces like "_semantic/does_not_exist"
        # must be rejected even when the top-level prefix exists.
        top_level = namespace.split("/")[0] if namespace else ""
        if not (namespace == top_level and top_level in valid_namespaces):
            errors.append(f"Unknown namespace '{namespace}'. Valid namespaces: {', '.join(sorted(valid_namespaces))}")

    # Validate type matches namespace prefix
    if namespace and memory_type:
        expected_type_map = {
            "_semantic": "semantic",
            "_episodic": "episodic",
            "_procedural": "procedural",
        }
        top_level = namespace.split("/")[0]
        expected_type = expected_type_map.get(top_level)
        if expected_type and memory_type != expected_type:
            errors.append(f"Type '{memory_type}' does not match namespace '{namespace}' (expected '{expected_type}')")

    return errors


def get_ontology_info() -> dict:
    """Get loaded ontology information including MIF base.

    Returns:
        Dict with ontology metadata, namespaces, entity types, traits,
        relationships, and discovery status.
    """
    info = {
        "loaded": False,
        "id": None,
        "version": None,
        "namespaces": [],
        "entity_types": [],
        "traits": {},
        "relationships": {},
        "discovery_enabled": False,
    }

    if not yaml:
        return info

    # Search paths for MIF ontology
    ontology_file = get_ontology_file()

    mif_data = None
    if ontology_file:
        mif_data = _load_yaml_file(ontology_file)
        if mif_data:
            info["loaded"] = True
            info["source"] = str(ontology_file)

    if mif_data:
        if "ontology" in mif_data:
            info["id"] = mif_data["ontology"].get("id")
            info["version"] = mif_data["ontology"].get("version")
        if "namespaces" in mif_data:
            ns_list = []
            _collect_namespaces(mif_data["namespaces"], "", ns_list)
            info["namespaces"] = ns_list
        info["entity_types"] = _extract_entity_type_names(mif_data)
        if "traits" in mif_data:
            info["traits"] = mif_data["traits"]
        if "relationships" in mif_data:
            info["relationships"] = mif_data["relationships"]
        if "discovery" in mif_data:
            info["discovery_enabled"] = mif_data["discovery"].get("enabled", False)

    # Also check custom ontologies (they extend MIF base). Every existing file
    # contributes (MIF 1.4.1 section 10.8.5); on conflicts the
    # higher-precedence file (earlier in get_ontology_paths) wins.
    custom_paths = get_v2_resolver().get_ontology_paths()
    loaded_paths = []
    datas = []
    for ont_path in custom_paths:
        if ont_path.exists():
            data = _load_yaml_file(ont_path)
            if isinstance(data, dict) and data:
                loaded_paths.append(ont_path)
                datas.append(data)

    if datas:
        data = merge_ontologies(datas)
        info["loaded"] = True
        info["custom_path"] = str(loaded_paths[0])
        info["custom_paths"] = [str(p) for p in loaded_paths]
        if isinstance(datas[0].get("ontology"), dict):
            info["custom_id"] = datas[0]["ontology"].get("id")
        if "namespaces" in data:
            ns_list = []
            _collect_namespaces(data["namespaces"], "", ns_list)
            info["namespaces"].extend(n for n in ns_list if n not in info["namespaces"])
        for name in _extract_entity_type_names(data):
            if name not in info["entity_types"]:
                info["entity_types"].append(name)
        if isinstance(data.get("traits"), dict):
            info["traits"].update(data["traits"])
        if isinstance(data.get("relationships"), dict):
            info["relationships"].update(data["relationships"])

    return info
