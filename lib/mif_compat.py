#!/usr/bin/env python3
"""
MIF 1.4.2 compatibility helpers.

mnemonic writes MIF (Modeled Information Format) 1.4.2 forms going forward
and keeps reading the legacy forms that memories written by older mnemonic
releases still carry on disk:

=====================================  ==========================================
Legacy form (still read)               MIF 1.4.2 form (written)
=====================================  ==========================================
snake_case concept frontmatter keys    camelCase keys (spec section 3.3), e.g.
(``valid_from``, ``source_type``,      ``validFrom``, ``sourceType``,
``compressed_at``, ...)                ``compressedAt``
relationship type ``relates_to`` /     kebab-case token ``relates-to``
``RelatesTo``                          (spec section 8.1.1)
relationship target ``<uuid>``         ``urn:mif:<uuid>`` (spec section 6.1)
relationship ``label``                 ``metadata.label`` (spec section 8.4)
body ``- relates-to [[<uuid>]]``       body ``- relates-to [Title](urn:mif:<uuid>)``
                                       mirrored under ``## Relationships``
                                       (spec section 5.3)
citation ``type``                      ``citationType`` (spec section 5.4)
=====================================  ==========================================

Readers should go through these helpers so both forms resolve identically,
always preferring the MIF 1.4.2 form when a file carries both.

This module is stdlib-only and Python 3.8 compatible: it is imported by
hooks, tools and the custodian skill.
"""

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Frontmatter key aliases (legacy snake_case -> MIF 1.4.2 camelCase)
# ---------------------------------------------------------------------------

# Keyed by the dotted path of the mapping that holds the keys ("" = top level).
# Only these known keys are renamed by the migration tool; unknown keys (and
# anything under ``extensions`` or relationship ``metadata``, which spec
# section 3.3 leaves unconstrained) are never touched.
LEGACY_KEY_ALIASES: Dict[str, Dict[str, str]] = {
    "": {
        "compressed_at": "compressedAt",
        "code_refs": "codeRefs",
    },
    "temporal": {
        "valid_from": "validFrom",
        "valid_until": "validUntil",
        "recorded_at": "recordedAt",
        "access_count": "accessCount",
        "last_accessed": "lastAccessed",
    },
    "temporal.decay": {
        "half_life": "halfLife",
    },
    "provenance": {
        "source_type": "sourceType",
        "source_ref": "sourceRef",
        "trust_level": "trustLevel",
        "agent_version": "agentVersion",
        "session_id": "sessionId",
    },
    "embedding": {
        "model_version": "modelVersion",
        "source_text": "sourceText",
        "vector_uri": "vectorUri",
    },
}

# Top-level fields older mnemonic capture templates wrote, which MIF 1.4.2
# places under provenance / temporal / temporal.decay. Still tolerated on
# read; tools/mnemonic-migrate-mif nests them. Maps to the MIF 1.4.2 path.
LEGACY_TOP_LEVEL_FIELDS: Dict[str, str] = {
    "confidence": "provenance.confidence",
    "strength": "temporal.decay.strength",
    "half_life": "temporal.decay.halfLife",
    "decay_model": "temporal.decay.model",
    "last_accessed": "temporal.lastAccessed",
}

# MIF 1.4.2 provenance.sourceType enum (spec section 12.1).
MIF_SOURCE_TYPES = (
    "user_explicit",
    "user_implicit",
    "agent_inferred",
    "external_import",
    "system_generated",
)

# sourceType values older mnemonic templates told agents to write. Still
# accepted on read (with a warning); never written by current templates.
LEGACY_SOURCE_TYPES = ("inferred", "conversation")

_CAMEL_SPLIT = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(key: str) -> str:
    """``validFrom`` -> ``valid_from`` (used to derive the legacy alias)."""
    return _CAMEL_SPLIT.sub("_", key).lower()


def get_compat(mapping: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` (camelCase) from ``mapping``, falling back to its legacy
    snake_case spelling. The MIF 1.4.2 key wins when both are present."""
    if not isinstance(mapping, dict):
        return default
    if mapping.get(key) is not None:
        return mapping[key]
    legacy = camel_to_snake(key)
    if legacy != key and mapping.get(legacy) is not None:
        return mapping[legacy]
    return default


def get_nested_compat(data: Any, *keys: str, default: Any = None) -> Any:
    """Nested :func:`get_compat`, e.g. ``get_nested_compat(fm, "temporal", "lastAccessed")``."""
    obj = data
    for k in keys:
        obj = get_compat(obj, k)
        if obj is None:
            return default
    return obj


def find_legacy_keys(frontmatter: Any) -> List[Tuple[str, str]]:
    """Return ``(legacy_path, new_path)`` for every legacy key present.

    Paths are dotted (``temporal.valid_from``). Used by validators to nudge
    toward the MIF 1.4.2 spelling without failing legacy files.
    """
    found: List[Tuple[str, str]] = []
    if not isinstance(frontmatter, dict):
        return found
    for container_path, aliases in LEGACY_KEY_ALIASES.items():
        container = _resolve(frontmatter, container_path)
        if not isinstance(container, dict):
            continue
        prefix = container_path + "." if container_path else ""
        for old, new in aliases.items():
            if old in container:
                found.append((prefix + old, prefix + new))
    for old, new in LEGACY_TOP_LEVEL_FIELDS.items():
        if old in frontmatter:
            found.append((old, new))
    return found


def _resolve(data: Any, dotted: str) -> Any:
    if not dotted:
        return data
    obj = data
    for part in dotted.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def _comment_items(mapping: Any) -> Optional[Dict[Any, Any]]:
    """ruamel.yaml per-key comment table, or None for a plain dict."""
    ca = getattr(mapping, "ca", None)
    items = getattr(ca, "items", None)
    return items if isinstance(items, dict) else None


def _rename_key(mapping: Any, old: str, new: str) -> None:
    """Rename a key in place, keeping its position and any attached comment
    (ruamel CommentedMap or plain dict)."""
    keys = list(mapping.keys())
    pos = keys.index(old)
    items = _comment_items(mapping)
    token = items.pop(old, None) if items is not None else None
    value = mapping.pop(old)
    if hasattr(mapping, "insert"):  # ruamel.yaml CommentedMap
        mapping.insert(pos, new, value)
        if token is not None and items is not None:
            items[new] = token
        return
    # Plain dict: rebuild to keep ordering
    items = list(mapping.items())
    items.insert(pos, (new, value))
    mapping.clear()
    for k, v in items:
        mapping[k] = v


def migrate_legacy_keys(frontmatter: Any) -> Tuple[List[str], List[str]]:
    """Rename known legacy keys to MIF 1.4.2 camelCase, in place.

    Returns ``(changes, conflicts)``. A conflict is a legacy key whose
    camelCase twin already exists; it is left untouched for a human to
    resolve (the camelCase value is what readers use).
    """
    changes: List[str] = []
    conflicts: List[str] = []
    for container_path, aliases in LEGACY_KEY_ALIASES.items():
        container = _resolve(frontmatter, container_path)
        if not isinstance(container, dict):
            continue
        prefix = container_path + "." if container_path else ""
        for old, new in aliases.items():
            if old not in container:
                continue
            if new in container:
                conflicts.append(f"{prefix}{old} (kept; {prefix}{new} already present)")
                continue
            _rename_key(container, old, new)
            changes.append(f"{prefix}{old} -> {prefix}{new}")
    return changes, conflicts


# ---------------------------------------------------------------------------
# Ontology merging (MIF 1.4.2 section 10.8.5)
# ---------------------------------------------------------------------------


def _merge_value(high: Any, low: Any) -> Any:
    if isinstance(high, dict) and isinstance(low, dict):
        for key, value in low.items():
            high[key] = _merge_value(high[key], value) if key in high else copy.deepcopy(value)
        return high
    if isinstance(high, list) and isinstance(low, list):
        named = {item.get("name") for item in high if isinstance(item, dict) and item.get("name")}
        for item in low:
            if isinstance(item, dict) and item.get("name"):
                if item["name"] in named:
                    continue  # higher-precedence definition wins
            elif item in high:
                continue
            high.append(copy.deepcopy(item))
        return high
    return high


def merge_ontologies(datas: List[Any]) -> Dict[str, Any]:
    """Merge parsed ontology documents, highest precedence first.

    Spec section 10.8.5: later (lower-precedence) sources are extended or
    overridden by earlier ones. Mappings merge recursively with the earlier
    value winning on conflict; lists are unioned (named entries such as
    ``entity_types`` deduplicated by ``name``). Inputs are not modified.
    """
    merged: Dict[str, Any] = {}
    for data in datas:
        if isinstance(data, dict):
            _merge_value(merged, data)
    return merged


# ---------------------------------------------------------------------------
# Relationship type tokens
# ---------------------------------------------------------------------------

KEBAB_TYPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(:[a-z0-9][a-z0-9-]*)?$")


def to_kebab(rel_type: str) -> str:
    """Normalize a relationship type to its MIF 1.4.2 kebab-case token.

    Accepts PascalCase (``DerivedFrom``), snake_case (``derived_from``) and
    kebab-case (``derived-from``), with an optional ``ns:`` prefix. Applies
    the spec section 8.1.1 rule (hyphen before every capital but the first).
    """
    if not rel_type:
        return ""
    text = str(rel_type).strip()
    prefix = ""
    if ":" in text:
        prefix, text = text.split(":", 1)
        prefix = prefix.strip().lower() + ":"
    text = _CAMEL_SPLIT.sub("-", text)
    text = text.replace("_", "-").replace(" ", "-").lower()
    text = re.sub(r"-+", "-", text).strip("-")
    return prefix + text


def is_kebab_type(rel_type: str) -> bool:
    """True when ``rel_type`` is already in MIF 1.4.2 token form."""
    return bool(KEBAB_TYPE_PATTERN.match(str(rel_type or "")))


# ---------------------------------------------------------------------------
# Relationship targets
# ---------------------------------------------------------------------------

UUID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
URN_PREFIX = "urn:mif:"


def target_ref(target: Any) -> str:
    """Return the bare reference for a relationship target.

    ``urn:mif:<uuid>`` and a JSON-LD ``{"@id": ...}`` node both reduce to
    ``<uuid>``; a bare UUID (legacy) is returned unchanged; any other string
    (e.g. a bundle-relative path) is returned stripped.
    """
    if isinstance(target, dict):
        target = target.get("@id", "")
    if target is None:
        return ""
    text = str(target).strip().strip('"').strip("'")
    if text.startswith(URN_PREFIX):
        rest = text[len(URN_PREFIX) :]
        if UUID_PATTERN.match(rest):
            return rest
    return text


def format_target(target: str) -> str:
    """Return the MIF 1.4.2 written form of a target: ``urn:mif:<uuid>`` for a
    UUID, otherwise the target unchanged (already a urn or a path)."""
    ref = target_ref(target)
    if UUID_PATTERN.match(ref):
        return URN_PREFIX + ref.lower()
    return str(target).strip()


def same_target(a: Any, b: Any) -> bool:
    """Compare two targets regardless of legacy/new spelling."""
    ra, rb = target_ref(a), target_ref(b)
    if UUID_PATTERN.match(ra) and UUID_PATTERN.match(rb):
        return ra.lower() == rb.lower()
    return ra == rb


def is_concept_target(target: Any) -> bool:
    """True for a reference to a MIF concept by id (``urn:mif:<uuid>`` or a
    bare UUID), as opposed to an arbitrary URL or path."""
    return bool(UUID_PATTERN.match(target_ref(target)))


# MIF 1.4.2 core relationship tokens (section 8.2), forward and inverse
CORE_RELATIONSHIP_TOKENS = frozenset(
    {
        "relates-to",
        "derived-from",
        "derives",
        "supersedes",
        "superseded-by",
        "conflicts-with",
        "part-of",
        "contains",
        "implements",
        "implemented-by",
        "uses",
        "used-by",
        "created",
        "created-by",
        "mentioned-in",
        "mentions",
    }
)


def is_relationship_type(rel_type: Any) -> bool:
    """True for a core MIF relationship type in any accepted spelling, or a
    namespaced custom type (``ns:type``)."""
    token = to_kebab(str(rel_type or ""))
    if token in CORE_RELATIONSHIP_TOKENS:
        return True
    return ":" in token and is_kebab_type(token)


def relationship_label(rel: Any) -> Optional[str]:
    """Return a relationship's label from ``metadata.label`` (1.4.2) or the
    legacy top-level ``label``."""
    if not isinstance(rel, dict):
        return None
    meta = rel.get("metadata")
    if isinstance(meta, dict) and meta.get("label"):
        return str(meta["label"])
    if rel.get("label"):
        return str(rel["label"])
    return None


# ---------------------------------------------------------------------------
# Body "## Relationships" section
# ---------------------------------------------------------------------------

RELATIONSHIPS_HEADING = "## Relationships"
_HEADING_RE = re.compile(r"^##\s+Relationships\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^#{1,2}\s+\S", re.MULTILINE)
# - relates-to [[uuid]]   or   - relates-to [[uuid|Display]]
WIKI_REL_LINE_RE = re.compile(r"^-\s+([A-Za-z0-9_:-]+)\s+\[\[([^\]|]+)(?:\|([^\]]*))?\]\]\s*$")
# - relates-to [Title](urn:mif:uuid)
MD_REL_LINE_RE = re.compile(r"^-\s+([A-Za-z0-9_:-]+)\s+\[([^\]]*)\]\(<?([^)\s>]+)>?\)\s*$")


def _section_span(body: str) -> Optional[Tuple[int, int]]:
    """Return (start, end) offsets of the ``## Relationships`` section content."""
    m = _HEADING_RE.search(body)
    if not m:
        return None
    start = m.end()
    nxt = _NEXT_HEADING_RE.search(body, start)
    end = nxt.start() if nxt else len(body)
    return start, end


def parse_body_relationships(body: str) -> List[Dict[str, str]]:
    """Parse relationship lines from the body ``## Relationships`` section.

    Recognizes both the MIF 1.4.2 markdown-link form and the legacy
    ``[[wiki-link]]`` form. Each entry has ``type`` (as written), ``target``
    (as written), ``text`` and ``form`` (``"markdown"`` or ``"wiki"``).
    """
    span = _section_span(body or "")
    if span is None:
        return []
    results: List[Dict[str, str]] = []
    for raw in body[span[0] : span[1]].splitlines():
        line = raw.strip()
        m = MD_REL_LINE_RE.match(line)
        if m:
            results.append({"type": m.group(1), "text": m.group(2), "target": m.group(3), "form": "markdown"})
            continue
        m = WIKI_REL_LINE_RE.match(line)
        if m:
            target = m.group(2).strip()
            text = (m.group(3) or "").strip() or target
            results.append({"type": m.group(1), "text": text, "target": target, "form": "wiki"})
    return results


def render_relationship_line(rel_type: str, target: str, text: Optional[str] = None) -> str:
    """Render one MIF 1.4.2 body mirror line: ``- <type> [Text](<target>)``."""
    shown = (text or target_ref(target) or target).replace("[", "(").replace("]", ")").strip()
    return f"- {to_kebab(rel_type)} [{shown}]({format_target(target)})"


def body_has_relationship(body: str, rel_type: str, target: Any) -> bool:
    """True if the body already mirrors this edge (either form)."""
    want_type = to_kebab(rel_type)
    for entry in parse_body_relationships(body):
        if to_kebab(entry["type"]) == want_type and same_target(entry["target"], target):
            return True
    return False


def upsert_body_relationship(body: str, rel_type: str, target: str, text: Optional[str] = None) -> str:
    """Return ``body`` with the edge mirrored in ``## Relationships``.

    No-op when an equivalent line (legacy wiki-link or markdown link) already
    exists. Otherwise appends a markdown-link line to the section, creating
    the section at the end of the body if absent.
    """
    body = body or ""
    if body_has_relationship(body, rel_type, target):
        return body
    line = render_relationship_line(rel_type, target, text)
    span = _section_span(body)
    if span is None:
        stripped = body.rstrip("\n")
        sep = "\n\n" if stripped else ""
        return f"{stripped}{sep}{RELATIONSHIPS_HEADING}\n\n{line}\n"
    start, end = span
    section = body[start:end].rstrip("\n")
    trailer = body[end:]
    new_section = f"{section}\n{line}\n" if section.strip() else f"\n\n{line}\n"
    if trailer:
        new_section += "\n"
    return body[:start] + new_section + trailer
