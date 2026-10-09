#!/usr/bin/env python3
"""
Ontology Loader for Mnemonic

Centralized loading of MIF ontologies with fallback support.
Loads from bundled ontologies, user, or project locations.
Caches loaded ontologies for session performance.

Canonical MIF schemas: https://mif-spec.dev/schema/
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

from .ontology_registry import DiscoveryPattern

logger = logging.getLogger(__name__)


def _mif_ontology_files(directory: Path) -> List[Path]:
    """``ontology.yaml`` plus every ``*.ontology.yaml`` in a ``.mif/ontologies/`` dir.

    Deliberate copy of ``lib.paths.mif_ontology_files``: this skill library
    is also imported with only ``skills/ontology/lib`` on ``sys.path``, where
    the top-level ``lib`` package is not importable. Keep the two in sync
    (``tests/unit/test_mif_141_alignment.py`` asserts they agree).
    """
    try:
        if not directory.is_dir():
            return []
        files: List[Path] = []
        plain = directory / "ontology.yaml"
        if plain.is_file():
            files.append(plain)
        files.extend(sorted(p for p in directory.rglob("*.ontology.yaml") if p.is_file()))
        return files
    except OSError:
        return []


@dataclass
class LoadedOntology:
    """A loaded and parsed ontology."""

    id: str
    version: str
    description: str = ""
    source_path: Optional[Path] = None

    # Hierarchical namespaces
    namespaces: Dict[str, Any] = field(default_factory=dict)

    # Entity types
    entity_types: List[Dict[str, Any]] = field(default_factory=list)

    # Traits
    traits: Dict[str, Any] = field(default_factory=dict)

    # Relationships
    relationships: Dict[str, Any] = field(default_factory=dict)

    # Discovery config
    discovery_enabled: bool = False
    confidence_threshold: float = 0.8
    discovery_patterns: List[DiscoveryPattern] = field(default_factory=list)


class OntologyLoader:
    """
    Loads MIF ontologies from multiple sources with caching.

    Resolution (MIF 1.4.2 section 10.8.5; later sources extend or override):
    1. Bundled MIF base ontology (skills/ontology/fallback/)
    2. User ontology: ``~/.mif/ontologies/`` (legacy fallback:
       ``~/.claude/mnemonic/{org}[/{project}]/ontology.yaml``)
    3. Project ontology: ``./.mif/ontologies/`` (legacy fallback:
       ``./.claude/mnemonic/ontology.yaml``)

    ``load_project_ontology`` returns the highest-precedence one found.

    Canonical MIF schemas: https://mif-spec.dev/schema/
    """

    # Canonical schema URLs
    MIF_SCHEMA_URL = "https://mif-spec.dev/schema/mif.schema.json"
    ONTOLOGY_SCHEMA_URL = "https://mif-spec.dev/schema/ontology/ontology.schema.json"

    def __init__(self, plugin_root: Optional[Path] = None):
        self._plugin_root = plugin_root or Path(__file__).parent.parent
        self._cache: Dict[str, LoadedOntology] = {}
        self._base_ontology: Optional[LoadedOntology] = None
        self._merged_patterns: Optional[List[DiscoveryPattern]] = None

    @property
    def fallback_path(self) -> Path:
        """Path to bundled ontologies."""
        return self._plugin_root / "fallback"

    def get_base_ontology_path(self) -> Optional[Path]:
        """Get path to base ontology from bundled fallback."""
        fallback_base = self.fallback_path / "ontologies" / "mif-base.ontology.yaml"
        if fallback_base.exists():
            return fallback_base

        return None

    def get_schema_path(self) -> Optional[Path]:
        """Get path to local ontology schema (bundled copy).

        For the canonical schema, use ONTOLOGY_SCHEMA_URL.
        """
        fallback_schema = self.fallback_path / "schema" / "ontology" / "ontology.schema.json"
        if fallback_schema.exists():
            return fallback_schema

        return None

    def load_base_ontology(self) -> Optional[LoadedOntology]:
        """Load the MIF base ontology."""
        if self._base_ontology is not None:
            return self._base_ontology

        base_path = self.get_base_ontology_path()
        if base_path is None:
            logger.warning("Base ontology not found in bundled fallback")
            return None

        self._base_ontology = self._load_ontology_file(base_path)
        return self._base_ontology

    def load_ontology(
        self,
        path: Path,
        use_cache: bool = True,
    ) -> Optional[LoadedOntology]:
        """Load an ontology from a specific path."""
        cache_key = str(path.absolute())

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        ontology = self._load_ontology_file(path)
        if ontology and use_cache:
            self._cache[cache_key] = ontology

        return ontology

    def load_project_ontologies(
        self,
        org: str = "default",
        project: Optional[str] = None,
    ) -> List[LoadedOntology]:
        """Load every project and user ontology, highest precedence first.

        Order: ``./.mif/ontologies/`` files, legacy ``./.claude/mnemonic/ontology.yaml``,
        ``~/.mif/ontologies/`` files, then the first legacy user ontology
        (``~/.claude/mnemonic/{org}/{project}/ontology.yaml`` or
        ``~/.claude/mnemonic/{org}/ontology.yaml``).
        """
        import re

        # Security: Validate org and project contain only safe characters
        if not re.match(r"^[a-zA-Z0-9_-]+$", org):
            logger.warning(f"Invalid org name contains unsafe characters: {org}")
            return []
        if project and not re.match(r"^[a-zA-Z0-9_-]+$", project):
            logger.warning(f"Invalid project name contains unsafe characters: {project}")
            return []

        candidates: List[Path] = []
        # Project-level: MIF 1.4.2 location first, then legacy
        candidates.extend(_mif_ontology_files(Path.cwd() / ".mif" / "ontologies"))
        candidates.append(Path.cwd() / ".claude" / "mnemonic" / "ontology.yaml")
        # User-level: MIF 1.4.2 location first, then the first legacy file found
        candidates.extend(_mif_ontology_files(Path.home() / ".mif" / "ontologies"))
        legacy_user = []
        if project:
            legacy_user.append(Path.home() / ".claude" / "mnemonic" / org / project / "ontology.yaml")
        legacy_user.append(Path.home() / ".claude" / "mnemonic" / org / "ontology.yaml")
        for legacy in legacy_user:
            if legacy.exists():
                candidates.append(legacy)
                break

        loaded: List[LoadedOntology] = []
        for path in candidates:
            if path.exists():
                ontology = self.load_ontology(path)
                if ontology:
                    loaded.append(ontology)
        return loaded

    def load_project_ontology(
        self,
        org: str = "default",
        project: Optional[str] = None,
    ) -> Optional[LoadedOntology]:
        """Load the highest-precedence project or user ontology, if any.

        See :meth:`load_project_ontologies` for the order; use that method
        to get every applicable ontology.
        """
        ontologies = self.load_project_ontologies(org, project)
        return ontologies[0] if ontologies else None

    def get_all_discovery_patterns(
        self,
        org: str = "default",
        project: Optional[str] = None,
    ) -> List[DiscoveryPattern]:
        """Get merged discovery patterns from all loaded ontologies."""
        if self._merged_patterns is not None:
            return self._merged_patterns

        patterns = []

        # Base ontology patterns
        base = self.load_base_ontology()
        if base and base.discovery_enabled:
            patterns.extend(base.discovery_patterns)

        # Project and user ontology patterns (every applicable file)
        for ontology in self.load_project_ontologies(org, project):
            if ontology.discovery_enabled:
                patterns.extend(ontology.discovery_patterns)

        self._merged_patterns = patterns
        return patterns

    def get_content_patterns(
        self,
        org: str = "default",
        project: Optional[str] = None,
    ) -> List[DiscoveryPattern]:
        """Get only content-based discovery patterns."""
        return [p for p in self.get_all_discovery_patterns(org, project) if p.pattern_type == "content"]

    def get_file_patterns(
        self,
        org: str = "default",
        project: Optional[str] = None,
    ) -> List[DiscoveryPattern]:
        """Get only file-based discovery patterns."""
        return [p for p in self.get_all_discovery_patterns(org, project) if p.pattern_type == "file"]

    def get_all_namespaces(self) -> List[str]:
        """Get all valid namespace paths from base ontology."""
        base = self.load_base_ontology()
        if not base:
            return []

        namespaces = []
        self._collect_namespace_paths(base.namespaces, "", namespaces)
        return namespaces

    def get_namespace_type_hint(self, namespace_path: str) -> str:
        """Get the type_hint for a namespace path."""
        base = self.load_base_ontology()
        if not base:
            return "semantic"

        parts = namespace_path.split("/")
        current = base.namespaces

        for part in parts:
            if part in current:
                ns_data = current[part]
                if isinstance(ns_data, dict):
                    if "children" in ns_data:
                        current = ns_data["children"]
                    if part == parts[-1]:
                        return ns_data.get("type_hint", "semantic")
            else:
                break

        return "semantic"

    def _collect_namespace_paths(
        self,
        namespaces: Dict[str, Any],
        prefix: str,
        result: List[str],
    ) -> None:
        """Recursively collect all namespace paths."""
        for name, data in namespaces.items():
            path = f"{prefix}/{name}" if prefix else name
            result.append(path)

            if isinstance(data, dict) and "children" in data:
                self._collect_namespace_paths(data["children"], path, result)

    def _load_ontology_file(self, path: Path) -> Optional[LoadedOntology]:
        """Load and parse a single ontology file."""
        if yaml is None:
            logger.warning("PyYAML not installed")
            return None

        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.error(f"Failed to load ontology {path}: {e}")
            return None

        if not data:
            return None

        return self._parse_ontology(data, path)

    def _parse_ontology(
        self,
        data: Dict[str, Any],
        source_path: Optional[Path] = None,
    ) -> LoadedOntology:
        """Parse ontology data into LoadedOntology."""
        ont_data = data.get("ontology", data)

        ontology = LoadedOntology(
            id=ont_data.get("id", "unknown"),
            version=str(ont_data.get("version", "1.0.0")),
            description=ont_data.get("description", ""),
            source_path=source_path,
            namespaces=data.get("namespaces", {}),
            entity_types=data.get("entity_types", []),
            traits=data.get("traits", {}),
            relationships=data.get("relationships", {}),
        )

        # Parse discovery config
        discovery = data.get("discovery", {})
        ontology.discovery_enabled = discovery.get("enabled", False)
        ontology.confidence_threshold = discovery.get("confidence_threshold", 0.8)

        patterns = []
        for p in discovery.get("patterns", []):
            if "content_pattern" in p:
                patterns.append(
                    DiscoveryPattern(
                        pattern_type="content",
                        pattern=p["content_pattern"],
                        suggest_entity=p.get("suggest_entity", ""),
                        suggest_namespace=p.get("suggest_namespace"),
                    )
                )
            elif "file_pattern" in p:
                patterns.append(
                    DiscoveryPattern(
                        pattern_type="file",
                        pattern=p["file_pattern"],
                        suggest_entity=p.get("suggest_entity", ""),
                        suggest_namespace=p.get("suggest_namespace"),
                    )
                )

        ontology.discovery_patterns = patterns

        return ontology

    def clear_cache(self) -> None:
        """Clear the ontology cache."""
        self._cache.clear()
        self._base_ontology = None
        self._merged_patterns = None


# Global loader instance
_loader: Optional[OntologyLoader] = None


def get_loader(plugin_root: Optional[Path] = None) -> OntologyLoader:
    """Get or create the global ontology loader.

    Args:
        plugin_root: Optional root path. Ignored if loader already exists
                     (use reset_loader() first to change roots).

    Returns:
        The global OntologyLoader instance.
    """
    global _loader
    if _loader is None:
        _loader = OntologyLoader(plugin_root)
    return _loader


def reset_loader() -> None:
    """Reset the global ontology loader.

    Use this when:
    - Plugin root has changed
    - Ontology files have been modified on disk
    - Tests need fresh state

    After calling this, the next get_loader() call will create a new instance.
    """
    global _loader
    if _loader is not None:
        _loader.clear_cache()
    _loader = None


def get_discovery_patterns(
    org: str = "default",
    project: Optional[str] = None,
) -> List[DiscoveryPattern]:
    """Convenience function to get discovery patterns."""
    return get_loader().get_all_discovery_patterns(org, project)


def get_namespaces() -> List[str]:
    """Convenience function to get all namespace paths."""
    return get_loader().get_all_namespaces()
