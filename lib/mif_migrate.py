#!/usr/bin/env python3
"""
Opt-in migration of legacy mnemonic memory files to MIF 1.4.2 forms.

Used by ``tools/mnemonic-migrate-mif``. Nothing in mnemonic calls this
automatically: readers already accept the legacy forms (see
``lib/mif_compat.py``), so migrating is optional.

Per file, :func:`plan_file` computes (without writing) the rewrite that:

1. renames legacy snake_case frontmatter keys to camelCase
   (``temporal.valid_from`` -> ``temporal.validFrom``,
   ``compressed_at`` -> ``compressedAt``, ...);
2. nests the top-level decay fields older capture templates wrote
   (``confidence``, ``strength``, ``half_life``, ``last_accessed``,
   ``decay_model``) under ``provenance`` / ``temporal`` / ``temporal.decay``;
3. rewrites relationships to kebab-case types and ``urn:mif:<uuid>``
   targets, moving a top-level ``label`` to ``metadata.label``;
4. renames citation ``type`` to ``citationType`` and adds
   ``"@type": Citation``;
5. converts ``## Relationships`` wiki-link lines (``- relates-to [[uuid]]``)
   to markdown links and makes frontmatter and body mirror each other
   (MIF 1.4.2 section 5.3).

It never renames files (mnemonic globs ``*.memory.md`` everywhere), never
changes values it cannot map mechanically (legacy ``sourceType`` values,
missing ``citationRole``), and leaves a key alone when its camelCase twin
already exists. Those cases are reported as notes for a human.

When frontmatter is unchanged it is kept as-is; when it changes it is
re-serialized with ruamel.yaml in round-trip mode, which keeps key order,
comments and quoting. CRLF files are written back with CRLF, and file
permissions are preserved.
"""

import io
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lib.mif_compat import (
    LEGACY_TOP_LEVEL_FIELDS,
    MIF_SOURCE_TYPES,
    UUID_PATTERN,
    WIKI_REL_LINE_RE,
    _comment_items,
    _rename_key,
    _section_span,
    format_target,
    get_compat,
    is_concept_target,
    is_kebab_type,
    is_relationship_type,
    migrate_legacy_keys,
    parse_body_relationships,
    render_relationship_line,
    same_target,
    target_ref,
    to_kebab,
    upsert_body_relationship,
)

try:  # ruamel.yaml is a declared dependency (pyproject.toml)
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
except ImportError:  # pragma: no cover - exercised only without ruamel
    YAML = None  # type: ignore[assignment,misc]
    CommentedMap = dict  # type: ignore[assignment,misc]

BACKUP_SUFFIX = ".pre-mif-1.4.1.bak"

# Top-level fields written by older capture templates -> (container path, key)
TOP_LEVEL_NESTING: Dict[str, Tuple[Tuple[str, ...], str]] = {
    old: (tuple(new.split(".")[:-1]), new.split(".")[-1]) for old, new in LEGACY_TOP_LEVEL_FIELDS.items()
}

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


class MigrationUnavailable(RuntimeError):
    """Raised when ruamel.yaml is not installed."""


@dataclass
class FilePlan:
    """What migrating one file would change."""

    path: Path
    changes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None
    original_text: Optional[str] = None  # newline-normalized (LF)
    new_text: Optional[str] = None  # LF; written with CRLF if the file used CRLF
    crlf: bool = False

    @property
    def changed(self) -> bool:
        return self.error is None and bool(self.changes) and self.new_text is not None


def _yaml() -> Any:
    if YAML is None:
        raise MigrationUnavailable("ruamel.yaml is required: pip install 'ruamel.yaml>=0.19.1'")
    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def split_document(text: str) -> Optional[Tuple[str, str]]:
    """Return ``(frontmatter_text, body)`` or None if there is no frontmatter."""
    m = _FM_RE.match(text)
    if not m:
        return None
    return m.group(1) or "", text[m.end() :]


def build_title_index(paths: Iterable[Path]) -> Dict[str, Dict[str, str]]:
    """Map ``uuid -> {"title", "slug"}`` and ``slug -> {"uuid", "title"}``.

    Used to give body links readable text and to resolve legacy slug
    wiki-links. Read-only; unparseable files are skipped.
    """
    index: Dict[str, Dict[str, str]] = {}
    y = _yaml()
    for p in paths:
        try:
            parts = split_document(p.read_text(encoding="utf-8"))
            if parts is None:
                continue
            fm = y.load(parts[0]) or {}
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue
        uid = str(fm.get("id", "")).strip()
        title = str(fm.get("title", "") or "").strip()
        slug = p.name[: -len(".memory.md")] if p.name.endswith(".memory.md") else p.stem
        if UUID_PATTERN.match(uid):
            index["uuid:" + uid.lower()] = {"title": title or slug, "slug": slug}
            index.setdefault("slug:" + slug, {"uuid": uid.lower(), "title": title or slug})
    return index


def _title_for(index: Dict[str, Dict[str, str]], target: str) -> Optional[str]:
    ref = target_ref(target)
    entry = index.get("uuid:" + ref.lower())
    return entry["title"] if entry else None


def _resolve_wiki_target(index: Dict[str, Dict[str, str]], raw: str) -> Optional[str]:
    """Wiki-link target -> written MIF target, or None if unresolvable."""
    ref = target_ref(raw)
    if UUID_PATTERN.match(ref):
        return format_target(ref)
    entry = index.get("slug:" + ref)
    if entry:
        return format_target(entry["uuid"])
    return None


def _move_key(src: Any, old: str, dst: Any, new: str, src_indent: int, dst_indent: int) -> None:
    """Move ``src[old]`` to ``dst[new]`` without losing its YAML comments.

    ruamel.yaml attaches a key's end-of-line comment, plus any full-line
    comments after it, to that key. The end-of-line comment follows the value
    to its new location (as a comment line above ``new``); trailing full-line
    comments stay where they were, above the next key of ``src``.
    """
    items = _comment_items(src)
    token = items.pop(old, None) if items is not None else None
    pos = list(src.keys()).index(old)
    dst[new] = src.pop(old)
    if not token or len(token) < 3 or token[2] is None:
        return
    lines = str(token[2].value).split("\n")
    eol = lines[0].strip().lstrip("#").strip()
    trailing = [line.strip().lstrip("#").strip() for line in lines[1:] if line.strip()]
    remaining = list(src.keys())
    nxt = remaining[pos] if pos < len(remaining) else None
    if trailing and nxt is None:
        # Nothing follows in src: keep the trailing lines with the moved value
        eol = "\n".join([eol] + trailing) if eol else "\n".join(trailing)
        trailing = []
    if eol and hasattr(dst, "yaml_set_comment_before_after_key"):
        dst.yaml_set_comment_before_after_key(new, before=eol, indent=dst_indent)
    if trailing and hasattr(src, "yaml_set_comment_before_after_key"):
        src.yaml_set_comment_before_after_key(nxt, before="\n".join(trailing), indent=src_indent)


def _ensure_map(parent: Any, key: str) -> Any:
    child = parent.get(key)
    if child is None:
        child = CommentedMap()
        parent[key] = child
    return child


def _nest_top_level(fm: Any, changes: List[str], notes: List[str]) -> None:
    for old, (container_path, new_key) in TOP_LEVEL_NESTING.items():
        if old not in fm:
            continue
        container: Any = fm
        blocked = False
        for part in container_path:
            existing = container.get(part)
            if existing is not None and not isinstance(existing, dict):
                blocked = True
                break
            container = _ensure_map(container, part)
        dotted = ".".join(container_path + (new_key,))
        if blocked:
            notes.append(f"kept top-level {old}: {'.'.join(container_path)} is not a mapping")
            continue
        if get_compat(container, new_key) is not None:
            notes.append(f"kept top-level {old}: {dotted} already present")
            continue
        _move_key(fm, old, container, new_key, src_indent=0, dst_indent=2 * len(container_path))
        changes.append(f"{old} -> {dotted}")


def _migrate_relationships(fm: Any, changes: List[str], notes: List[str]) -> List[Tuple[str, str]]:
    """Rewrite frontmatter relationships; return [(type, target)] in written form."""
    edges: List[Tuple[str, str]] = []
    rels = fm.get("relationships")
    if not isinstance(rels, list):
        return edges
    for i, rel in enumerate(rels):
        if not isinstance(rel, dict):
            continue
        rtype = rel.get("type")
        target = rel.get("target")
        if rtype and not is_kebab_type(str(rtype)):
            rel["type"] = to_kebab(str(rtype))
            changes.append(f"relationships[{i}].type {rtype} -> {rel['type']}")
        if isinstance(target, dict) and isinstance(target.get("@id"), str):
            # JSON-LD node form {"@id": ...} -> the plain string form
            rel["target"] = format_target(target_ref(target))
            changes.append(f"relationships[{i}].target {{'@id'}} -> {rel['target']}")
        elif isinstance(target, str) and target.strip() != format_target(target):
            rel["target"] = format_target(target)
            changes.append(f"relationships[{i}].target -> {rel['target']}")
        if "label" in rel:
            meta = rel.get("metadata")
            if meta is not None and not isinstance(meta, dict):
                notes.append(f"relationships[{i}].label kept: metadata is not a mapping")
            elif isinstance(meta, dict) and meta.get("label") is not None:
                notes.append(f"relationships[{i}].label kept: metadata.label already present")
            else:
                meta = _ensure_map(rel, "metadata")
                # list items sit at column 4 (sequence indent 4, offset 2)
                _move_key(rel, "label", meta, "label", src_indent=4, dst_indent=6)
                changes.append(f"relationships[{i}].label -> metadata.label")
        if rel.get("type") and isinstance(rel.get("target"), str):
            edges.append((str(rel["type"]), str(rel["target"])))
    return edges


def _migrate_citations(fm: Any, changes: List[str], notes: List[str]) -> None:
    cites = fm.get("citations")
    if not isinstance(cites, list):
        return
    for i, cite in enumerate(cites):
        if not isinstance(cite, dict):
            continue
        if "type" in cite and "citationType" not in cite:
            _rename_key(cite, "type", "citationType")
            changes.append(f"citations[{i}].type -> citationType")
        if "@type" not in cite:
            if hasattr(cite, "insert"):
                cite.insert(0, "@type", "Citation")
            else:
                cite["@type"] = "Citation"
            changes.append(f'citations[{i}] add "@type": Citation')
        if "citationRole" not in cite:
            notes.append(f"citations[{i}] has no citationRole (MIF 1.4.2 requires one; not inferred)")


def _migrate_body(
    body: str,
    edges: List[Tuple[str, str]],
    index: Dict[str, Dict[str, str]],
    changes: List[str],
    notes: List[str],
) -> Tuple[str, List[Tuple[str, str]]]:
    """Convert wiki-link relationship lines and mirror frontmatter edges.

    Returns ``(new_body, body_only_edges)`` where ``body_only_edges`` are body
    relationships with no frontmatter entry (to be added to frontmatter).
    """
    span = _section_span(body)
    outside_text = body[: span[0]] + body[span[1] :] if span else body
    outside = WIKI_LINK_RE.findall(outside_text)
    if outside:
        notes.append(f"{len(outside)} inline [[...]] link(s) outside ## Relationships left as prose")

    if span is not None:
        start, end = span
        new_lines = []
        for raw in body[start:end].split("\n"):
            m = WIKI_REL_LINE_RE.match(raw.strip())
            if not m:
                new_lines.append(raw)
                continue
            target = _resolve_wiki_target(index, m.group(2).strip())
            if target is None:
                notes.append(f"wiki-link [[{m.group(2).strip()}]] kept: target not found")
                new_lines.append(raw)
                continue
            text = (m.group(3) or "").strip() or _title_for(index, target) or target_ref(target)
            new_lines.append(render_relationship_line(m.group(1), target, text))
            changes.append(f"body wiki-link [[{m.group(2).strip()}]] -> markdown link")
        body = body[:start] + "\n".join(new_lines) + body[end:]

    # Every frontmatter edge needs a body mirror line
    for rtype, target in edges:
        updated = upsert_body_relationship(body, rtype, target, _title_for(index, target))
        if updated != body:
            changes.append(f"body mirror added: {to_kebab(rtype)} {target}")
            body = updated

    # Body edges with no frontmatter entry
    # Only lines that are unambiguously MIF edges qualify: a known relationship
    # type and a concept target (urn:mif:<uuid>). Ordinary prose links such as
    # "- Related [RFC](https://...)" are left alone.
    body_only: List[Tuple[str, str]] = []
    for entry in parse_body_relationships(body):
        if entry["form"] != "markdown":
            continue
        if not is_concept_target(entry["target"]) or not is_relationship_type(entry["type"]):
            continue
        if not any(to_kebab(t) == to_kebab(entry["type"]) and same_target(tg, entry["target"]) for t, tg in edges):
            body_only.append((to_kebab(entry["type"]), format_target(entry["target"])))
    return body, body_only


def plan_file(path: Path, index: Optional[Dict[str, Dict[str, str]]] = None) -> FilePlan:
    """Compute the MIF 1.4.2 rewrite for one file. Never writes."""
    plan = FilePlan(path=path)
    index = index or {}
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8").replace("\r\n", "\n")
    except Exception as exc:
        plan.error = f"unreadable: {exc}"
        return plan
    plan.crlf = b"\r\n" in raw
    plan.original_text = text
    parts = split_document(text)
    if parts is None:
        plan.error = "no YAML frontmatter"
        return plan
    fm_text, body = parts

    y = _yaml()
    try:
        fm = y.load(fm_text) if fm_text.strip() else CommentedMap()
    except Exception as exc:
        plan.error = f"frontmatter is not valid YAML: {exc}"
        return plan
    if not isinstance(fm, dict):
        plan.error = "frontmatter is not a mapping"
        return plan

    fm_changes: List[str] = []
    renamed, conflicts = migrate_legacy_keys(fm)
    fm_changes.extend(renamed)
    plan.notes.extend(f"kept legacy key {c}" for c in conflicts)
    _nest_top_level(fm, fm_changes, plan.notes)
    edges = _migrate_relationships(fm, fm_changes, plan.notes)
    _migrate_citations(fm, fm_changes, plan.notes)

    source_type = get_compat(fm.get("provenance"), "sourceType")
    if source_type is not None and source_type not in MIF_SOURCE_TYPES:
        plan.notes.append(f"provenance.sourceType {source_type!r} is not a MIF 1.4.2 value; left as-is")

    body_changes: List[str] = []
    new_body, body_only = _migrate_body(body, edges, index, body_changes, plan.notes)
    if body_only:
        rels = fm.get("relationships")
        if rels is None:
            rels = []
            fm["relationships"] = rels
        if isinstance(rels, list):
            for rtype, target in body_only:
                entry = CommentedMap()
                entry["type"] = rtype
                entry["target"] = target
                rels.append(entry)
                fm_changes.append(f"relationships += {rtype} {target} (from body)")
        else:
            plan.notes.append("body relationships not added: frontmatter relationships is not a list")

    plan.changes = fm_changes + body_changes
    if not plan.changes:
        return plan

    if fm_changes:
        buf = io.StringIO()
        y.dump(fm, buf)
        new_fm = buf.getvalue()
        if not new_fm.endswith("\n"):
            new_fm += "\n"
        plan.new_text = f"---\n{new_fm}---\n{new_body}"
    else:
        # Frontmatter untouched: keep it (and its delimiters) as written
        plan.new_text = text[: len(text) - len(body)] + new_body
    return plan


def apply_plan(plan: FilePlan, backup: bool = True) -> Optional[Path]:
    """Write a planned rewrite atomically. Returns the backup path, if any."""
    if not plan.changed or plan.new_text is None:
        return None
    path = plan.path
    backup_path: Optional[Path] = None
    if backup:
        backup_path = path.with_name(path.name + BACKUP_SUFFIX)
        if not backup_path.exists():  # keep the oldest original
            shutil.copy2(str(path), str(backup_path))  # keeps permissions
    data = plan.new_text.replace("\n", "\r\n") if plan.crlf else plan.new_text
    tmp = path.with_name(path.name + ".mif-migrate.tmp")
    try:
        tmp.write_bytes(data.encode("utf-8"))
        shutil.copymode(str(path), str(tmp))  # a 0600 memory stays 0600
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return backup_path


def find_memory_files(paths: Iterable[Path]) -> Tuple[List[Path], List[str]]:
    """Collect ``*.memory.md`` files under ``paths`` (deduplicated, sorted).

    Symlinked files are skipped (reported) so a migration never writes
    through a link into another tree.
    """
    seen = set()
    files: List[Path] = []
    skipped: List[str] = []
    for root in paths:
        candidates: List[Path]
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(root.rglob("*.memory.md"))
        else:
            skipped.append(f"{root}: not found")
            continue
        for p in candidates:
            if not p.name.endswith(".memory.md"):
                skipped.append(f"{p}: not a .memory.md file")
                continue
            if p.is_symlink():
                skipped.append(f"{p}: symlink skipped")
                continue
            key = p.resolve()
            if key in seen:
                continue
            seen.add(key)
            files.append(p)
    return files, skipped
