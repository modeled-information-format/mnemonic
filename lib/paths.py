#!/usr/bin/env python3
"""
Mnemonic Path Resolution Library

Centralized path resolution for all mnemonic memory operations.
Provides a single source of truth for path construction with support
for migration from legacy path schemes.

Design Goals:
- Single source of truth for all path logic
- Support legacy and new path schemes during migration
- Testable and mockable for unit tests
- Clean abstraction that makes future changes easy

Path Schemes:
- LEGACY: Dual location (user + project) with flat namespace
- V2 (Target): Unified user-level with project hierarchy

Examples:
    # Get memory file path
    resolver = PathResolver()
    path = resolver.get_memory_path(
        namespace="_semantic/decisions",
        scope="project"
    )

    # Get search paths for recall
    paths = resolver.get_search_paths(
        namespace="_semantic/decisions",
        include_project=True
    )
"""

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from lib.config import MnemonicConfig

# MIF 1.4.2 ontology directory, relative to a project root or the home
# directory (spec section 10.8.5: `.mif/ontologies/` and `~/.mif/ontologies/`).
MIF_ONTOLOGY_DIR = Path(".mif") / "ontologies"


def mif_ontology_files(directory: Path) -> List[Path]:
    """List ontology files in a MIF ``.mif/ontologies/`` directory.

    Returns ``ontology.yaml`` (if present) followed by every
    ``*.ontology.yaml`` beneath the directory, sorted. Missing or unreadable
    directories yield an empty list. Mirrored by ``_mif_ontology_files`` in
    ``skills/ontology/lib/ontology_loader.py``; keep them in sync.
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


class PathScheme(Enum):
    """Path scheme versions for migration support."""

    LEGACY = "legacy"  # Current: dual location, flat namespace
    V2 = "v2"  # Target: unified user-level, project hierarchy


class Scope(Enum):
    """Memory scope for organization."""

    USER = "user"  # Cross-project memories
    PROJECT = "project"  # Project-specific memories
    ORG = "org"  # Organization-wide memories (V2 only)


@dataclass
class PathContext:
    """Context information for path resolution."""

    org: str
    project: str
    home_dir: Path
    project_dir: Path
    memory_root: Path
    scheme: PathScheme = PathScheme.LEGACY

    @classmethod
    def detect(cls, scheme: PathScheme = PathScheme.LEGACY) -> "PathContext":
        """Detect context from environment."""
        config = MnemonicConfig.load()
        remote_url = _get_git_remote_url()
        return cls(
            org=_detect_org(remote_url),
            project=_detect_project(remote_url),
            home_dir=Path.home(),
            project_dir=Path.cwd(),
            memory_root=config.memory_store_path,
            scheme=scheme,
        )


class PathResolver:
    """
    Central path resolver for all mnemonic operations.

    This class encapsulates all path construction logic, enabling:
    - Easy testing via dependency injection
    - Migration between path schemes
    - Consistent path resolution across all components
    """

    def __init__(self, context: Optional[PathContext] = None):
        """
        Initialize resolver with context.

        Args:
            context: Path context. If None, will auto-detect.
        """
        self.context = context or PathContext.detect()

    def get_memory_dir(
        self,
        namespace: str,
        scope: Scope = Scope.PROJECT,
    ) -> Path:
        """
        Get directory for storing memories.

        Args:
            namespace: Hierarchical namespace (e.g., "_semantic/decisions")
            scope: Memory scope (user, project, or org)

        Returns:
            Path to memory directory

        Examples:
            # LEGACY scheme, project scope
            get_memory_dir("_semantic/decisions", Scope.PROJECT)
            # => ./.claude/mnemonic/semantic/decisions

            # V2 scheme, project scope
            get_memory_dir("_semantic/decisions", Scope.PROJECT)
            # => {memory_root}/{org}/{project}/semantic/decisions

            # V2 scheme, org scope
            get_memory_dir("_semantic/decisions", Scope.ORG)
            # => {memory_root}/{org}/semantic/decisions
        """
        if self.context.scheme == PathScheme.LEGACY:
            return self._get_legacy_memory_dir(namespace, scope)
        else:
            return self._get_v2_memory_dir(namespace, scope)

    def get_memory_path(
        self,
        namespace: str,
        filename: str,
        scope: Scope = Scope.PROJECT,
    ) -> Path:
        """
        Get full path to a memory file.

        Args:
            namespace: Hierarchical namespace
            filename: Memory filename (should end with .memory.md)
            scope: Memory scope

        Returns:
            Full path to memory file
        """
        directory = self.get_memory_dir(namespace, scope)
        return directory / filename

    def get_search_paths(
        self,
        namespace: Optional[str] = None,
        include_user: bool = True,
        include_project: bool = True,
        include_org: bool = False,
    ) -> List[Path]:
        """
        Get ordered list of paths to search for memories.

        Search order priority:
        1. Project-specific memories
        2. Organization-wide memories (V2 only)
        3. User cross-project memories

        Args:
            namespace: Optional namespace filter
            include_user: Include user-scope paths
            include_project: Include project-scope paths
            include_org: Include org-scope paths (V2 only)

        Returns:
            List of paths to search, in priority order
        """
        if self.context.scheme == PathScheme.LEGACY:
            return self._get_legacy_search_paths(namespace, include_user, include_project)
        else:
            return self._get_v2_search_paths(namespace, include_user, include_project, include_org)

    def get_blackboard_dir(
        self,
        scope: Scope = Scope.PROJECT,
    ) -> Path:
        """
        Get blackboard directory for session coordination.

        Args:
            scope: Blackboard scope (project or org)

        Returns:
            Path to blackboard directory
        """
        if self.context.scheme == PathScheme.LEGACY:
            if scope == Scope.PROJECT:
                return self.context.project_dir / ".claude" / "mnemonic" / ".blackboard"
            else:
                return self.context.memory_root / ".blackboard"
        else:
            if scope == Scope.PROJECT:
                base = self.context.memory_root / self.context.org / self.context.project
                return base / ".blackboard"
            else:
                return self.context.memory_root / self.context.org / ".blackboard"

    def get_session_blackboard_dir(self, session_id: str, scope: Scope = Scope.PROJECT) -> Path:
        """Get session-scoped blackboard directory."""
        bb = self.get_blackboard_dir(scope)
        return bb / "sessions" / session_id

    def get_handoff_dir(self, scope: Scope = Scope.PROJECT) -> Path:
        """Get handoff directory for session handoffs."""
        bb = self.get_blackboard_dir(scope)
        return bb / "handoff"

    def get_legacy_blackboard_dir(self, scope: Scope = Scope.PROJECT) -> Path:
        """Get legacy blackboard directory (for migration)."""
        bb = self.get_blackboard_dir(scope)
        return bb / "_legacy"

    def list_session_blackboards(self, scope: Scope = Scope.PROJECT, active_only: bool = False) -> list:
        """List session blackboard directories."""
        bb = self.get_blackboard_dir(scope)
        sessions_dir = bb / "sessions"
        if not sessions_dir.exists():
            return []
        dirs = sorted(sessions_dir.iterdir())
        if active_only:
            import json

            active = []
            for d in dirs:
                meta = d / "_meta.json"
                if meta.exists():
                    try:
                        data = json.loads(meta.read_text())
                        if data.get("status") == "active":
                            active.append(d)
                    except Exception:
                        pass
            return active
        return [d for d in dirs if d.is_dir()]

    def get_ontology_paths(self) -> List[Path]:
        """
        Get ordered list of ontology file paths to check.

        MIF 1.4.2 (spec section 10.8.5) locations are checked first; the
        locations used by earlier mnemonic releases remain as fallbacks so
        existing custom ontologies keep loading.

        Returns:
            List of ontology paths in precedence order (first wins where a
            caller picks one; later entries are lower priority when merged):
            1. Project ontologies: ``<project>/.mif/ontologies/**/*.ontology.yaml``
               (and ``<project>/.mif/ontologies/ontology.yaml``)
            2. Legacy project ontology (``.claude/mnemonic/ontology.yaml`` or
               ``${MNEMONIC_ROOT}/{org}/{project}/ontology.yaml``)
            3. User ontologies: ``~/.mif/ontologies/**/*.ontology.yaml``
               (and ``~/.mif/ontologies/ontology.yaml``)
            4. Legacy user/org ontology (``${MNEMONIC_ROOT}/ontology.yaml`` or
               ``${MNEMONIC_ROOT}/{org}/ontology.yaml``)

            The bundled MIF base ontology is loaded separately by
            ``lib.ontology``. MIF directory entries are included only when the
            file exists; legacy entries are always listed (callers check
            ``exists()``), as before.
        """
        paths: List[Path] = []

        # 1. Project ontologies (MIF 1.4.2)
        paths.extend(mif_ontology_files(self.context.project_dir / MIF_ONTOLOGY_DIR))

        # 2. Legacy project ontology
        if self.context.scheme == PathScheme.LEGACY:
            paths.append(self.context.project_dir / ".claude" / "mnemonic" / "ontology.yaml")
        else:
            paths.append(self.context.memory_root / self.context.org / self.context.project / "ontology.yaml")

        # 3. User ontologies (MIF 1.4.2)
        paths.extend(mif_ontology_files(self.context.home_dir / MIF_ONTOLOGY_DIR))

        # 4. Legacy user/org ontology
        if self.context.scheme == PathScheme.LEGACY:
            paths.append(self.context.memory_root / "ontology.yaml")
        else:
            paths.append(self.context.memory_root / self.context.org / "ontology.yaml")

        return paths

    def get_all_memory_roots(self) -> List[Path]:
        """
        Get all root directories that may contain memories.

        Useful for operations like:
        - Garbage collection across all memories
        - Health checks
        - Migration scripts

        Returns:
            List of all memory root directories
        """
        if self.context.scheme == PathScheme.LEGACY:
            roots = []
            user_base = self.context.memory_root

            # User org directory
            org_path = user_base / self.context.org
            if org_path.exists():
                roots.append(org_path)

            # Default directory
            default_path = user_base / "default"
            if default_path.exists():
                roots.append(default_path)

            # Project directory
            project_path = self.context.project_dir / ".claude" / "mnemonic"
            if project_path.exists():
                roots.append(project_path)

            return roots
        else:
            # V2: Everything is under memory_root
            base = self.context.memory_root / self.context.org
            return [base] if base.exists() else []

    # Legacy scheme implementations

    def _get_legacy_memory_dir(self, namespace: str, scope: Scope) -> Path:
        """Get memory directory using legacy path scheme."""
        if scope == Scope.PROJECT:
            return self.context.project_dir / ".claude" / "mnemonic" / namespace
        else:
            return self.context.memory_root / self.context.org / namespace

    def _get_legacy_search_paths(
        self,
        namespace: Optional[str],
        include_user: bool,
        include_project: bool,
    ) -> List[Path]:
        """Get search paths using legacy scheme."""
        paths = []

        if include_project:
            project_base = self.context.project_dir / ".claude" / "mnemonic"
            if namespace:
                paths.append(project_base / namespace)
            else:
                paths.append(project_base)

        if include_user:
            user_base = self.context.memory_root

            # Org-specific memories
            org_base = user_base / self.context.org
            if namespace:
                paths.append(org_base / namespace)
            else:
                paths.append(org_base)

            # Default fallback
            default_base = user_base / "default"
            if namespace:
                paths.append(default_base / namespace)
            else:
                paths.append(default_base)

        return [p for p in paths if p.exists()]

    # V2 scheme implementations

    def _get_v2_memory_dir(self, namespace: str, scope: Scope) -> Path:
        """Get memory directory using V2 path scheme."""
        base = self.context.memory_root / self.context.org

        if scope == Scope.PROJECT:
            return base / self.context.project / namespace
        elif scope == Scope.ORG:
            return base / namespace
        else:  # USER scope - store in "shared" or under project
            return base / self.context.project / namespace

    def _get_v2_search_paths(
        self,
        namespace: Optional[str],
        include_user: bool,
        include_project: bool,
        include_org: bool,
    ) -> List[Path]:
        """Get search paths using V2 scheme."""
        paths = []
        base = self.context.memory_root / self.context.org

        # Project-specific (highest priority)
        if include_project:
            project_base = base / self.context.project
            if namespace:
                paths.append(project_base / namespace)
            else:
                paths.append(project_base)

        # Org-wide
        if include_org:
            if namespace:
                paths.append(base / namespace)
            else:
                paths.append(base)

        # Default fallback (for backward compatibility)
        if include_user:
            default_base = self.context.memory_root / "default"
            if namespace:
                paths.append(default_base / namespace)
            else:
                paths.append(default_base)

        return [p for p in paths if p.exists()]


# Helper functions for context detection


def _get_git_remote_url() -> Optional[str]:
    """Get the git remote origin URL, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_org_from_url(url: str) -> str:
    """Extract organization name from a git remote URL."""
    if ":" in url and "@" in url:
        # SSH format: git@github.com:org/repo.git
        return url.split(":")[-1].split("/")[0].replace(".git", "")
    # HTTPS format: https://github.com/org/repo.git
    parts = url.rstrip(".git").split("/")
    return parts[-2] if len(parts) >= 2 else "default"


def _parse_project_from_url(url: str) -> str:
    """Extract project name from a git remote URL."""
    return url.rstrip(".git").split("/")[-1]


def _detect_org(remote_url: Optional[str] = None) -> str:
    """Detect organization from git remote. Falls back to 'default'."""
    url = remote_url if remote_url is not None else _get_git_remote_url()
    return _parse_org_from_url(url) if url else "default"


def _detect_project(remote_url: Optional[str] = None) -> str:
    """Detect project name from git remote, toplevel dir, or cwd."""
    url = remote_url if remote_url is not None else _get_git_remote_url()
    if url:
        return _parse_project_from_url(url)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    return Path.cwd().name


# Convenience functions for backward compatibility

_SCOPE_MAP = {
    "user": Scope.USER,
    "project": Scope.PROJECT,
    "org": Scope.ORG,
}


def _parse_scope(scope: str, default: Scope = Scope.PROJECT) -> Scope:
    """Convert a scope string to Scope enum."""
    return _SCOPE_MAP.get(scope, default)


def get_default_resolver() -> PathResolver:
    """Get default path resolver with auto-detected context."""
    return PathResolver()


def get_memory_dir(namespace: str, scope: str = "project") -> Path:
    """Convenience function for getting memory directory."""
    return get_default_resolver().get_memory_dir(namespace, _parse_scope(scope))


def get_search_paths(
    namespace: Optional[str] = None,
    include_user: bool = True,
    include_project: bool = True,
) -> List[Path]:
    """Convenience function for getting search paths."""
    return get_default_resolver().get_search_paths(namespace, include_user, include_project)


def get_blackboard_dir(scope: str = "project") -> Path:
    """Convenience function for getting blackboard directory."""
    return get_default_resolver().get_blackboard_dir(_parse_scope(scope))


def get_session_blackboard_dir(session_id: str, scope: str = "project") -> Path:
    """Convenience function for getting session blackboard directory."""
    return get_default_resolver().get_session_blackboard_dir(session_id, _parse_scope(scope))


def get_handoff_dir(scope: str = "project") -> Path:
    """Convenience function for getting handoff directory."""
    return get_default_resolver().get_handoff_dir(_parse_scope(scope))


# Blackboard migration


def migrate_blackboard_to_session_scoped(bb_root: Path) -> bool:
    """Migrate flat blackboard to session-scoped structure.

    Idempotent: returns False if already migrated (_legacy/ exists).
    """
    legacy_dir = bb_root / "_legacy"
    if legacy_dir.exists():
        return False  # Already migrated

    # Check if there's anything to migrate
    md_files = list(bb_root.glob("*.md"))
    if not md_files:
        # Nothing to migrate, just create the structure
        (bb_root / "sessions").mkdir(parents=True, exist_ok=True)
        (bb_root / "handoff").mkdir(parents=True, exist_ok=True)
        return True

    # Create new structure
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (bb_root / "sessions").mkdir(parents=True, exist_ok=True)
    (bb_root / "handoff").mkdir(parents=True, exist_ok=True)

    # Move existing md files to _legacy/
    for md_file in md_files:
        dest = legacy_dir / md_file.name
        md_file.rename(dest)

    # Extract latest handoff from legacy session-notes.md
    legacy_notes = legacy_dir / "session-notes.md"
    if legacy_notes.exists():
        try:
            content = legacy_notes.read_text()
            # Find last entry (after last ---)
            parts = content.split("---")
            if len(parts) > 1:
                last_entry = parts[-1].strip()
                if last_entry:
                    handoff_content = f"# Latest Handoff (migrated from legacy)\n\n---\n{last_entry}\n"
                    (bb_root / "handoff" / "latest-handoff.md").write_text(handoff_content)
        except Exception:
            pass

    return True


# Shared V2 resolver for hooks and tools

_v2_resolver: Optional[PathResolver] = None


def get_v2_resolver() -> PathResolver:
    """Get or create a shared V2-scheme PathResolver instance."""
    global _v2_resolver
    if _v2_resolver is None:
        context = PathContext.detect(scheme=PathScheme.V2)
        _v2_resolver = PathResolver(context)
    return _v2_resolver


def get_all_memory_roots_with_legacy() -> List[Path]:
    """Get all memory root paths, including legacy paths during migration.

    Combines PathResolver.get_all_memory_roots() with legacy org/default dirs.
    """
    resolver = get_v2_resolver()
    root = MnemonicConfig.load().memory_store_path
    roots = resolver.get_all_memory_roots()
    legacy_roots = [
        root / resolver.context.org,
        root / "default",
    ]
    return list(set(roots + [p for p in legacy_roots if p.exists()]))
