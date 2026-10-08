"""MIF schema and ontological relationship validation."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.mif_compat import find_legacy_keys, to_kebab

from .memory_file import MemoryFile
from .report import Report

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from lib.relationships import get_all_valid_types
    from lib.relationships import is_valid_type as _is_valid_rel_type
except ImportError:
    _is_valid_rel_type = None  # type: ignore[assignment]
    get_all_valid_types = None  # type: ignore[assignment]


# Valid MIF relationship types — imported from canonical registry when available,
# with hardcoded fallback for standalone use.
if get_all_valid_types is not None:
    VALID_RELATIONSHIP_TYPES = get_all_valid_types()
else:
    VALID_RELATIONSHIP_TYPES = {
        "RelatesTo",
        "DerivedFrom",
        "Supersedes",
        "ConflictsWith",
        "PartOf",
        "Implements",
        "Uses",
        "Created",
        "MentionedIn",
        # Inverse types
        "Derives",
        "SupersededBy",
        "Contains",
        "ImplementedBy",
        "UsedBy",
        "CreatedBy",
        "Mentions",
    }

# Valid provenance source types
VALID_SOURCE_TYPES = {
    "user_explicit",
    "user_implicit",
    "agent_inferred",
    "external_import",
    "system_generated",
    "conversation",
    "extraction",
    "codebase_analysis",
    "system",
}

# Patterns that indicate a placeholder rather than a real value
_PLACEHOLDER_ID_PATTERNS = {
    "${UUID}",
    "PLACEHOLDER_UUID",
    "MEMORY_ID_PLACEHOLDER",
}
_PLACEHOLDER_DATE_PATTERNS = {
    "${DATE}",
    "PLACEHOLDER_DATE",
    "DATE_PLACEHOLDER",
}


def _is_placeholder_id(uid: str) -> bool:
    """Check if a UUID value is a placeholder that should be replaced."""
    if uid in _PLACEHOLDER_ID_PATTERNS:
        return True
    # Also catch template-style like ${...}
    if uid.startswith("${") and uid.endswith("}"):
        return True
    return False


def _is_placeholder_date(date_str: str) -> bool:
    """Check if a date value is a placeholder that should be replaced."""
    if date_str in _PLACEHOLDER_DATE_PATTERNS:
        return True
    if date_str.startswith("${") and date_str.endswith("}"):
        return True
    return False


def _get_file_date(path: Path) -> str:
    """Get an ISO date from the file's mtime, falling back to now."""
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except OSError:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def validate_memories(roots: List[Path], report: Report, fix: bool = False) -> int:
    """Validate memory frontmatter completeness against MIF schema.

    When fix=True, auto-repairs:
    - Placeholder UUIDs (${UUID}, PLACEHOLDER_UUID, etc.) -> real UUIDs
    - Invalid/non-standard UUIDs -> real UUIDs
    - Placeholder dates (${DATE}, PLACEHOLDER_DATE, etc.) -> file mtime
    - Invalid date formats -> file mtime

    Returns number of memories with errors.
    """
    error_count = 0

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.memory.md")):
            mem = MemoryFile(path)
            errors = mem.validate_frontmatter()
            needs_save = False

            for err in errors:
                fixed = False

                if fix and "Invalid UUID format:" in err:
                    # Extract the bad UUID from the error message
                    bad_id = err.split("Invalid UUID format:")[-1].strip()
                    new_id = str(uuid.uuid4())
                    mem.update_field_in_raw("id", new_id)
                    report.error(
                        "frontmatter",
                        f"Invalid UUID '{bad_id}' replaced with {new_id}",
                        file_path=path,
                        fixed=True,
                    )
                    needs_save = True
                    fixed = True

                if fix and "Invalid created date format:" in err:
                    bad_date = err.split("Invalid created date format:")[-1].strip()
                    new_date = _get_file_date(path)
                    mem.update_field_in_raw("created", new_date)
                    report.error(
                        "frontmatter",
                        f"Invalid date '{bad_date}' replaced with {new_date}",
                        file_path=path,
                        fixed=True,
                    )
                    needs_save = True
                    fixed = True

                if not fixed:
                    report.error("frontmatter", err, file_path=path)
                    error_count += 1

            if fix and needs_save:
                mem.save()

            # Additional checks beyond basic required fields

            # Check namespace matches directory structure
            ns = mem.namespace
            if ns:
                expected_parts = ns.replace("_", "").split("/")
                path_parts = [p for p in path.parent.parts if p not in (".", "..")]
                # Namespace should appear in path
                ns_found = any(part in path_parts for part in expected_parts)
                if not ns_found:
                    report.warning(
                        "frontmatter",
                        f"Namespace '{ns}' doesn't match directory path",
                        file_path=path,
                    )

            # Check provenance sourceType (MIF 1.4.1), falling back to legacy source_type
            source_type = mem.get_compat("provenance", "sourceType")
            if source_type and str(source_type) not in VALID_SOURCE_TYPES:
                report.warning(
                    "frontmatter",
                    f"Unknown provenance sourceType: {source_type}",
                    file_path=path,
                )

            # Legacy snake_case keys are still read, but MIF 1.4.1 uses camelCase
            legacy = find_legacy_keys(mem.frontmatter)
            if legacy:
                report.info(
                    "frontmatter",
                    "Legacy key(s) "
                    + ", ".join(f"{old} (MIF 1.4.1: {new})" for old, new in legacy)
                    + "; see tools/mnemonic-migrate-mif",
                    file_path=path,
                )

            # Check confidence range
            confidence = mem.get_nested("provenance", "confidence")
            if confidence is not None:
                try:
                    conf_val = float(confidence)
                    if not 0.0 <= conf_val <= 1.0:
                        report.error(
                            "frontmatter",
                            f"Confidence {conf_val} out of range [0.0, 1.0]",
                            file_path=path,
                        )
                except (ValueError, TypeError):
                    report.error(
                        "frontmatter",
                        f"Invalid confidence value: {confidence}",
                        file_path=path,
                    )

    return error_count


def validate_relationships(
    roots: List[Path],
    report: Report,
    ontology_data: Optional[Dict[str, Any]] = None,
) -> int:
    """Validate ontological relationship types and targets.

    Args:
        roots: Memory root directories
        report: Report to accumulate findings
        ontology_data: Loaded ontology YAML data (optional, for custom relationships)

    Returns:
        Number of relationship errors found.
    """
    # Build set of valid relationship types (built-in + ontology custom)
    valid_types = set(VALID_RELATIONSHIP_TYPES)
    if ontology_data and "relationships" in ontology_data:
        for rel_name in ontology_data["relationships"]:
            valid_types.add(rel_name)
            # Also add PascalCase variant
            valid_types.add(rel_name.replace("_", " ").title().replace(" ", ""))
            # And the MIF 1.4.1 kebab-case token
            valid_types.add(to_kebab(rel_name))

    error_count = 0

    def _check_rel_type(rel_type_str: str) -> bool:
        """Check if a relationship type is valid (supports both naming conventions)."""
        if rel_type_str in valid_types or to_kebab(rel_type_str) in valid_types:
            return True
        # Use canonical registry if available (handles snake_case + PascalCase)
        if _is_valid_rel_type is not None:
            return _is_valid_rel_type(rel_type_str)
        return False

    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.memory.md")):
            mem = MemoryFile(path)
            rels = mem.get("relationships")
            if not isinstance(rels, list):
                continue

            for rel in rels:
                if not isinstance(rel, dict):
                    report.error(
                        "relationships",
                        "Relationship entry is not a mapping",
                        file_path=path,
                    )
                    error_count += 1
                    continue

                rel_type = rel.get("relationshipType") or rel.get("type", "")
                if rel_type and not _check_rel_type(str(rel_type)):
                    report.error(
                        "relationships",
                        f"Unknown relationship type: {rel_type}",
                        file_path=path,
                    )
                    error_count += 1

                # Check target exists
                target = rel.get("target")
                if target is None:
                    report.error(
                        "relationships",
                        "Relationship missing target",
                        file_path=path,
                    )
                    error_count += 1

                # Check strength range if present
                strength = rel.get("strength")
                if strength is not None:
                    try:
                        s_val = float(strength)
                        if not 0.0 <= s_val <= 1.0:
                            report.warning(
                                "relationships",
                                f"Relationship strength {s_val} out of range [0.0, 1.0]",
                                file_path=path,
                            )
                    except (ValueError, TypeError):
                        report.warning(
                            "relationships",
                            f"Invalid relationship strength: {strength}",
                            file_path=path,
                        )

    return error_count


def load_ontology(ontology_paths: List[Path]) -> Optional[Dict[str, Any]]:
    """Load the first available ontology file.

    Args:
        ontology_paths: Ordered list of paths to check

    Returns:
        Parsed ontology data or None
    """
    if yaml is None:
        return None
    for ont_path in ontology_paths:
        if ont_path.exists():
            try:
                with open(ont_path) as f:
                    return yaml.safe_load(f)
            except Exception:
                continue
    return None
