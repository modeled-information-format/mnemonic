#!/usr/bin/env python3
"""
Mnemonic Memory Reader

Shared helper for reading memory file summaries and metadata.
Used by hooks to inject actual memory content instead of bare file paths.
"""

import re
from pathlib import Path
from typing import Optional

from lib.mif_compat import relationship_label

try:
    import yaml
except ImportError:
    yaml = None


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter text using yaml.safe_load with regex fallback.

    Args:
        text: Raw frontmatter text (without --- delimiters).

    Returns:
        Parsed dict of frontmatter fields.
    """
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass  # Fall through to regex fallback
    return _regex_fallback_parse(text)


def _regex_fallback_parse(text: str) -> dict:
    """Regex-based frontmatter parsing fallback when PyYAML unavailable.

    Extracts top-level scalar fields, inline list tags, multi-line list tags,
    and relationship blocks.
    """
    fm: dict = {}

    # Extract id (UUIDs may contain any alphanumeric chars + hyphens)
    id_match = re.search(r"^id:\s*([a-zA-Z0-9-]+)", text, re.MULTILINE)
    if id_match:
        fm["id"] = id_match.group(1).strip()

    # Extract title
    title_match = re.search(r"^title:\s*[\"']?([^\"'\n]+)", text, re.MULTILINE)
    if title_match:
        fm["title"] = title_match.group(1).strip()

    # Extract namespace
    namespace_match = re.search(r"^namespace:\s*([^\n]+)", text, re.MULTILINE)
    if namespace_match:
        fm["namespace"] = namespace_match.group(1).strip()

    # Extract type
    type_match = re.search(r"^type:\s*([^\n]+)", text, re.MULTILINE)
    if type_match:
        fm["type"] = type_match.group(1).strip()

    # Extract tags (inline list)
    tags_match = re.search(r"^tags:\s*\[([^\]]+)\]", text, re.MULTILINE)
    if tags_match:
        tags_str = tags_match.group(1)
        fm["tags"] = [tag.strip().strip('"').strip("'") for tag in tags_str.split(",") if tag.strip()]
    else:
        # Try multi-line YAML list format
        tags_section = re.search(r"^tags:\s*\n((?:  - .+\n?)+)", text, re.MULTILINE)
        if tags_section:
            tag_lines = tags_section.group(1).strip().split("\n")
            fm["tags"] = [line.strip().lstrip("- ").strip('"').strip("'") for line in tag_lines if line.strip()]

    # Extract relationships block — handles both:
    #   - type: foo\n    target: bar   (YAML block sequence)
    #   - type: foo\n  - type: baz     (compact)
    rel_header = re.search(r"^relationships:\s*\n", text, re.MULTILINE)
    if rel_header:
        relationships = []
        # Grab everything after "relationships:\n" until next top-level key or end
        rest = text[rel_header.end() :]
        block_end = re.search(r"^\S", rest, re.MULTILINE)
        rel_text = rest[: block_end.start()] if block_end else rest
        # Split on list item markers
        rel_blocks = re.split(r"(?:^|\n)  - ", rel_text)
        for block in rel_blocks:
            if not block.strip():
                continue
            rel: dict = {}
            type_m = re.search(r"type:\s*([^\n]+)", block)
            # Targets may be a bare UUID (legacy), urn:mif:<uuid> or a bundle path
            target_m = re.search(r"target:\s*[\"']?([^\s\"']+)", block)
            # label (legacy, top-level) or metadata.label (MIF 1.4.2)
            label_m = re.search(r"label:\s*[\"']?([^\"'\n]+)", block)
            if type_m:
                rel["type"] = type_m.group(1).strip()
            if target_m:
                rel["target"] = target_m.group(1).strip()
            if label_m:
                rel["label"] = label_m.group(1).strip()
            if rel.get("type") and rel.get("target"):
                relationships.append(rel)
        fm["relationships"] = relationships

    return fm


def get_memory_summary(path: str, max_summary: int = 300) -> dict:
    """Read a memory file and extract title + summary.

    Args:
        path: Absolute or relative path to a .memory.md file.
        max_summary: Maximum characters for the summary text.

    Returns:
        dict with keys: title (str), summary (str).
        Falls back to filename stem if parsing fails.
    """
    try:
        p = Path(path)
        if not p.exists():
            return {"title": p.stem, "summary": ""}

        content = p.read_bytes()[:1500].decode("utf-8", errors="replace")

        # Extract title from YAML frontmatter
        title = p.stem
        title_match = re.search(r"title:\s*[\"']?([^\"'\n]+)", content)
        if title_match:
            title = title_match.group(1).strip()

        # Extract summary: first non-frontmatter paragraph
        summary = ""
        in_frontmatter = False
        past_frontmatter = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    past_frontmatter = True
                    in_frontmatter = False
                continue
            if past_frontmatter and stripped and not stripped.startswith("#"):
                summary = stripped
                break

        if len(summary) > max_summary:
            summary = summary[: max_summary - 3] + "..."

        return {"title": title, "summary": summary}
    except Exception:
        return {"title": Path(path).stem, "summary": ""}


def get_memory_metadata(path: str, max_summary: int = 300) -> Optional[dict]:
    """Read a memory file and extract full metadata including relationships.

    Uses yaml.safe_load when available, with regex fallback for environments
    without PyYAML.

    Args:
        path: Absolute or relative path to a .memory.md file.
        max_summary: Maximum characters for the summary text.

    Relationship entries are returned as written (``type`` and ``target``
    keep their on-disk spelling, legacy or MIF 1.4.2); ``label`` is read from
    MIF 1.4.2 ``metadata.label`` or the legacy top-level ``label``. Use
    ``lib.mif_compat.to_kebab`` / ``target_ref`` to compare them.

    Returns:
        dict with keys: id, title, namespace, tags, relationships, summary, path.
        Returns None if file doesn't exist or can't be read.
    """
    try:
        p = Path(path)
        if not p.exists():
            return None

        # Read first 2000 bytes (enough for frontmatter + first paragraph)
        content = p.read_bytes()[:2000].decode("utf-8", errors="replace")

        # Initialize metadata with defaults
        metadata = {
            "id": None,
            "title": p.stem,
            "namespace": None,
            "tags": [],
            "relationships": [],
            "summary": "",
            "path": str(p.absolute()),
        }

        # Split frontmatter from body
        in_frontmatter = False
        past_frontmatter = False
        frontmatter_lines = []
        content_lines = []

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    past_frontmatter = True
                    in_frontmatter = False
                continue

            if in_frontmatter:
                frontmatter_lines.append(line)
            elif past_frontmatter:
                content_lines.append(line)

        # Parse frontmatter using YAML (with regex fallback)
        frontmatter_text = "\n".join(frontmatter_lines)
        fm = _parse_frontmatter(frontmatter_text)

        # Map parsed fields to metadata
        if fm.get("id"):
            raw_id = str(fm["id"]).strip().strip('"').strip("'")
            metadata["id"] = raw_id

        if fm.get("title"):
            metadata["title"] = str(fm["title"]).strip().strip('"').strip("'")

        if fm.get("namespace"):
            metadata["namespace"] = str(fm["namespace"]).strip()

        if isinstance(fm.get("tags"), list):
            metadata["tags"] = [str(t).strip().strip('"').strip("'") for t in fm["tags"] if t]
        elif isinstance(fm.get("tags"), str):
            metadata["tags"] = [t.strip() for t in fm["tags"].split(",") if t.strip()]

        # Extract relationships
        rels = fm.get("relationships")
        if isinstance(rels, list):
            parsed_rels = []
            for rel in rels:
                if isinstance(rel, dict):
                    parsed_rel: dict = {}
                    if rel.get("type"):
                        parsed_rel["type"] = str(rel["type"]).strip()
                    if rel.get("target"):
                        parsed_rel["target"] = str(rel["target"]).strip()
                    label = relationship_label(rel)
                    if label:
                        parsed_rel["label"] = label.strip()
                    if parsed_rel.get("type") and parsed_rel.get("target"):
                        parsed_rels.append(parsed_rel)
            metadata["relationships"] = parsed_rels

        # Extract summary: first non-frontmatter, non-heading paragraph
        for line in content_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                metadata["summary"] = stripped
                break

        if len(metadata["summary"]) > max_summary:
            metadata["summary"] = metadata["summary"][: max_summary - 3] + "..."

        return metadata
    except Exception:
        return None
