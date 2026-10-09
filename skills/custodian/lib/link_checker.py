"""Link validation and repair for memory files."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .memory_file import UUID_PATTERN, MemoryFile
from .report import Report

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "we",
        "i",
        "you",
        "it",
        "do",
        "did",
        "does",
        "have",
        "has",
        "had",
        "what",
        "how",
        "why",
        "when",
        "about",
        "this",
        "that",
        "there",
        "here",
        "with",
        "for",
        "to",
        "from",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "of",
        "as",
        "by",
        "not",
        "no",
    }
)


class LinkIndex:
    """Index of all memory files by UUID and slug for fast lookup."""

    def __init__(self) -> None:
        self._by_uuid: Dict[str, Path] = {}
        self._by_slug: Dict[str, Path] = {}
        self._all_paths: Set[Path] = set()
        self.collisions: List[Tuple[str, Path, Path]] = []  # (key, existing, new)

    @staticmethod
    def _get_project_dir(path: Path, root: Path) -> str:
        """Get the project-level directory for a memory path.

        Given root=/a/b/zircote and path=/a/b/zircote/myproject/_semantic/foo.memory.md,
        returns 'myproject'.
        """
        try:
            rel = path.relative_to(root)
            return rel.parts[0] if rel.parts else ""
        except ValueError:
            return ""

    def build(self, roots: List[Path]) -> None:
        """Scan all memory roots and build UUID/slug indexes."""
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.memory.md"):
                self._all_paths.add(path)
                mem = MemoryFile(path)
                uid = mem.uuid
                if uid:
                    if uid in self._by_uuid:
                        self.collisions.append(("uuid:" + uid, self._by_uuid[uid], path))
                    self._by_uuid[uid] = path
                slug = mem.slug
                if slug:
                    if slug in self._by_slug:
                        # Only flag slug collision if both files are in the same project dir
                        existing = self._by_slug[slug]
                        existing_proj = self._get_project_dir(existing, root)
                        new_proj = self._get_project_dir(path, root)
                        if existing_proj == new_proj:
                            self.collisions.append(("slug:" + slug, existing, path))
                    self._by_slug[slug] = path

    def resolve(self, ref: str) -> Optional[Path]:
        """Resolve a reference (UUID or slug) to a file path."""
        ref_clean = ref.strip().replace("urn:mif:", "")
        if UUID_PATTERN.match(ref_clean):
            return self._by_uuid.get(ref_clean)
        return self._by_slug.get(ref_clean)

    def find_references_to(self, target_path: Path) -> List[Tuple[Path, str]]:
        """Find all memories that reference the target (by UUID or slug)."""
        target_mem = MemoryFile(target_path)
        target_uuid = target_mem.uuid or ""
        target_slug = target_mem.slug

        refs: List[Tuple[Path, str]] = []
        for path in self._all_paths:
            if path == target_path:
                continue
            mem = MemoryFile(path)
            for link in mem.find_wiki_links():
                if link == target_uuid or link == target_slug:
                    refs.append((path, link))
            for rel_target in mem.find_relationship_targets():
                if rel_target == target_uuid or rel_target == target_slug:
                    refs.append((path, rel_target))
        return refs

    @property
    def all_paths(self) -> Set[Path]:
        return self._all_paths

    def has_uuid(self, uid: str) -> bool:
        return uid in self._by_uuid

    def has_slug(self, slug: str) -> bool:
        return slug in self._by_slug


def validate_links(roots: List[Path], report: Report, fix: bool = False) -> LinkIndex:
    """Validate all wiki-links and frontmatter relationships.

    Returns the built LinkIndex for reuse by other operations.
    """
    index = LinkIndex()
    index.build(roots)

    # Report any UUID/slug collisions
    for key, existing, duplicate in index.collisions:
        report.warning(
            "collisions",
            f"Duplicate {key}: {existing.name} and {duplicate.name}",
            file_path=duplicate,
        )

    for path in sorted(index.all_paths):
        mem = MemoryFile(path)

        # Check wiki-links in body
        for link in mem.find_wiki_links():
            resolved = index.resolve(link)
            if resolved is None:
                if fix:
                    # Remove broken wiki-link, replace with plain text
                    mem.replace_in_body(f"[[{link}]]", link)
                    report.error(
                        "links",
                        f"Broken wiki-link [[{link}]] removed",
                        file_path=path,
                        fixed=True,
                    )
                else:
                    report.error(
                        "links",
                        f"Broken wiki-link: [[{link}]]",
                        file_path=path,
                    )

        # Check frontmatter relationship targets
        for target_id in mem.find_relationship_targets():
            # Skip wiki-links already checked above
            if target_id in mem.find_wiki_links():
                continue
            resolved = index.resolve(target_id)
            if resolved is None:
                report.error(
                    "relationships",
                    f"Relationship target not found: {target_id}",
                    file_path=path,
                )

        if fix and mem._dirty:
            mem.save()

    return index


def ensure_bidirectional(
    index: LinkIndex,
    report: Report,
    fix: bool = False,
) -> int:
    """Find relationships missing their inverse back-reference.

    For each relationship A->B of type T, checks if B has the corresponding
    inverse relationship back to A. If missing and fix=True, creates it.

    Args:
        index: Pre-built LinkIndex from validate_links().
        report: Report to accumulate findings.
        fix: If True, auto-create missing back-references.

    Returns:
        Count of missing back-references found.
    """
    try:
        from lib.mif_compat import same_target, target_ref, to_kebab
        from lib.relationships import add_relationship, get_inverse, is_symmetric, is_valid_type
    except ImportError:
        report.warning("bidirectional", "lib.relationships not available, skipping bidirectional check")
        return 0

    missing_count = 0

    for path in sorted(index.all_paths):
        mem = MemoryFile(path)
        source_uuid = mem.uuid
        if not source_uuid:
            continue

        rels = mem.get("relationships")
        if not isinstance(rels, list):
            continue

        for rel in rels:
            if not isinstance(rel, dict):
                continue

            rel_type = rel.get("type", "")
            # str, urn:mif:<uuid>, or a JSON-LD {"@id": ...} node
            target_id = target_ref(rel.get("target", ""))
            if not rel_type or not target_id:
                continue

            # Skip unknown relationship types to avoid creating incorrect back-refs
            if not is_valid_type(rel_type):
                report.warning(
                    "bidirectional",
                    f"Unknown relationship type '{rel_type}', skipping bidirectional check",
                    file_path=path,
                )
                continue

            # Resolve target to a file path
            target_path = index.resolve(target_id)
            if target_path is None:
                continue  # Broken link, handled by validate_links

            # Check if target has the inverse relationship back
            target_mem = MemoryFile(target_path)
            target_rels = target_mem.get("relationships")
            # Compare on MIF 1.4.2 kebab-case tokens so legacy spellings
            # (PascalCase, snake_case) and new ones match each other.
            inverse_token = to_kebab(get_inverse(rel_type))

            # Build the set of acceptable back-ref types:
            # - The proper inverse
            # - relates-to as a weaker but acceptable back-ref
            # - For symmetric types, the forward type is also valid
            acceptable_types = {inverse_token, "relates-to"}
            if is_symmetric(rel_type):
                acceptable_types.add(to_kebab(rel_type))

            has_back_ref = False
            if isinstance(target_rels, list):
                for trel in target_rels:
                    if not isinstance(trel, dict):
                        continue
                    trel_type = to_kebab(trel.get("type", ""))
                    trel_target = trel.get("target", "")
                    if same_target(trel_target, source_uuid) and trel_type in acceptable_types:
                        has_back_ref = True
                        break

            if not has_back_ref:
                missing_count += 1
                # New back-refs are always written in MIF 1.4.2 form
                back_ref_type = inverse_token

                if fix:
                    added = add_relationship(
                        str(target_path),
                        back_ref_type,
                        source_uuid,
                        label=f"Auto back-ref from {path.stem}",
                        target_title=mem.title,
                    )
                    report.info(
                        "bidirectional",
                        f"Missing {back_ref_type} back-ref from {target_path.name} -> {path.name}"
                        + (" (FIXED)" if added else " (failed to fix)"),
                        file_path=target_path,
                        fixed=added,
                    )
                else:
                    report.warning(
                        "bidirectional",
                        f"Missing {back_ref_type} back-ref: {target_path.name} should have "
                        f"{back_ref_type} -> {source_uuid[:12]}... ({path.name})",
                        file_path=target_path,
                    )

    return missing_count


def find_orphans(index: LinkIndex) -> List[Path]:
    """Find memory files with no incoming references."""
    referenced: Set[Path] = set()

    for path in index.all_paths:
        mem = MemoryFile(path)
        for link in mem.find_wiki_links():
            resolved = index.resolve(link)
            if resolved:
                referenced.add(resolved)
        for target_id in mem.find_relationship_targets():
            resolved = index.resolve(target_id)
            if resolved:
                referenced.add(resolved)

    return sorted(index.all_paths - referenced)


def _extract_keywords(text: str) -> Set[str]:
    """Extract keywords from text for matching."""
    words = re.sub(r"[^\w\s]", "", text.lower()).split()
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _get_project_from_path(path: Path) -> str:
    """Extract project name from memory path (first dir after org root)."""
    parts = path.parts
    # Find the cognitive triad dir (_semantic, _procedural, _episodic) and take one before
    for i, part in enumerate(parts):
        if part.startswith("_") and part.lstrip("_") in ("semantic", "procedural", "episodic"):
            return parts[i - 1] if i > 0 else ""
    return ""


def link_orphans(
    index: LinkIndex,
    orphans: List[Path],
    report: Report,
) -> int:
    """Link orphaned memories to their best-matching related memory.

    Scoring signals:
    - Same project directory: +20
    - Same cognitive type (_semantic, _procedural, _episodic): +15
    - Same sub-namespace: +10
    - Shared title keywords: +10 per keyword
    - Shared tags: +10 per tag

    Threshold is adaptive: memories in projects with <=2 files use a lower
    threshold (15) since they can't get the project bonus from peers.
    Memories in larger projects require 30 (project + one signal).

    Returns count of orphans that were linked.
    """
    try:
        from lib.relationships import add_bidirectional_relationship
    except ImportError:
        report.warning("orphans", "lib.relationships not available, cannot link orphans")
        return 0

    # Pre-compute metadata for all memories
    all_meta: Dict[Path, Dict] = {}
    for path in index.all_paths:
        mem = MemoryFile(path)
        title = mem.title or ""
        ns = mem.namespace or ""
        tags_raw = mem.get("tags")
        tags: Set[str] = set()
        if isinstance(tags_raw, list):
            tags = {str(t).lower() for t in tags_raw if t}
        all_meta[path] = {
            "uuid": mem.uuid,
            "title": title,
            "namespace": ns,
            "tags": tags,
            "keywords": _extract_keywords(title),
            "project": _get_project_from_path(path),
            "cognitive_type": ns.split("/")[0] if ns else "",
        }

    # Count memories per project to identify small projects
    from collections import Counter

    project_sizes: Counter = Counter()
    for meta in all_meta.values():
        if meta["project"]:
            project_sizes[meta["project"]] += 1

    linked = 0

    for orphan_path in orphans:
        orphan = all_meta.get(orphan_path)
        if not orphan or not orphan["uuid"]:
            continue

        best_score = 0
        best_path: Optional[Path] = None

        for candidate_path, candidate in all_meta.items():
            if candidate_path == orphan_path:
                continue
            if not candidate["uuid"]:
                continue

            score = 0

            # Same project directory
            if orphan["project"] and orphan["project"] == candidate["project"]:
                score += 20

            # Same cognitive type
            if orphan["cognitive_type"] and orphan["cognitive_type"] == candidate["cognitive_type"]:
                score += 15

            # Same sub-namespace
            if orphan["namespace"] and orphan["namespace"] == candidate["namespace"]:
                score += 10

            # Shared title keywords
            shared_kw = orphan["keywords"] & candidate["keywords"]
            score += len(shared_kw) * 10

            # Shared tags
            shared_tags = orphan["tags"] & candidate["tags"]
            score += len(shared_tags) * 10

            if score > best_score:
                best_score = score
                best_path = candidate_path

        # Adaptive threshold: small/solo projects can't get the +20 project bonus
        # from peers, so lower the bar to cognitive type + one keyword (15+10=25)
        proj_size = project_sizes.get(orphan["project"], 0)
        threshold = 25 if proj_size <= 2 else 30

        if best_score >= threshold and best_path is not None:
            fwd, rev = add_bidirectional_relationship(
                str(orphan_path),
                str(best_path),
                "RelatesTo",
                label="Auto-linked by custodian (orphan)",
            )
            if fwd or rev:
                linked += 1
                report.info(
                    "orphans",
                    f"Linked to {best_path.name} (score={best_score})",
                    file_path=orphan_path,
                    fixed=True,
                )

    return linked
