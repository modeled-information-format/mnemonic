"""Lightweight MemoryFile abstraction for reading/writing MIF frontmatter."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from lib.mif_compat import get_nested_compat, is_concept_target, parse_body_relationships, target_ref

# Required MIF fields
REQUIRED_FIELDS = {"id", "type", "title", "created"}
VALID_TYPES = {"semantic", "episodic", "procedural"}
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?")
WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def _find_frontmatter_end(content: str) -> Optional[int]:
    """Find character offset of closing --- delimiter, line-by-line."""
    if not content.startswith("---"):
        return None
    lines = content.split("\n")
    offset = len(lines[0]) + 1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return offset
        offset += len(lines[i]) + 1
    return None


def _split_raw(content: str) -> Tuple[str, str]:
    """Split content into raw frontmatter block (with delimiters) and body."""
    end_offset = _find_frontmatter_end(content)
    if end_offset is None:
        return "", content
    closing_end = content.find("\n", end_offset)
    if closing_end == -1:
        closing_end = end_offset + 3
    else:
        closing_end += 1
    return content[:closing_end].rstrip("\n"), content[closing_end:].strip()


class MemoryFile:
    """Lightweight wrapper for a .memory.md file."""

    def __init__(self, path: Path, content: Optional[str] = None):
        self.path = path
        self._raw = content if content is not None else path.read_text()
        self._fm_block, self._body = _split_raw(self._raw)
        self._frontmatter = self._parse_frontmatter()
        self._dirty = False

    def _parse_frontmatter(self) -> Dict[str, Any]:
        if not self._fm_block:
            return {}
        fm_text = self._fm_block.strip()
        if fm_text.startswith("---"):
            fm_text = fm_text[3:]
        if fm_text.endswith("---"):
            fm_text = fm_text[:-3]
        fm_text = fm_text.strip()
        if yaml is not None:
            try:
                data = yaml.safe_load(fm_text)
                return data if isinstance(data, dict) else {}
            except Exception:
                pass
        # Fallback: line-by-line top-level key parsing
        fm: Dict[str, Any] = {}
        for line in fm_text.splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                key, _, value = line.partition(":")
                fm[key.strip()] = value.strip()
        return fm

    @property
    def frontmatter(self) -> Dict[str, Any]:
        return self._frontmatter

    @property
    def body(self) -> str:
        return self._body

    def get(self, key: str, default: Any = None) -> Any:
        return self._frontmatter.get(key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested value, e.g. get_nested('temporal', 'decay', 'model').

        Keys are matched exactly; use :meth:`get_compat` for fields whose
        legacy snake_case spelling should also be accepted.
        """
        obj: Any = self._frontmatter
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
            else:
                return default
        return obj if obj is not None else default

    def get_compat(self, *keys: str, default: Any = None) -> Any:
        """Nested lookup preferring MIF 1.4.1 camelCase keys, falling back to
        the legacy snake_case spelling, e.g. get_compat('temporal', 'lastAccessed')."""
        return get_nested_compat(self._frontmatter, *keys, default=default)

    @property
    def uuid(self) -> Optional[str]:
        val = self.get("id", "")
        if isinstance(val, str):
            return val.strip().strip('"').strip("'")
        return None

    @property
    def title(self) -> Optional[str]:
        val = self.get("title", "")
        if isinstance(val, str):
            return val.strip().strip('"').strip("'")
        return None

    @property
    def memory_type(self) -> Optional[str]:
        return self.get("type")

    @property
    def namespace(self) -> Optional[str]:
        return self.get("namespace")

    @property
    def slug(self) -> str:
        return self.path.stem.replace(".memory", "")

    def find_wiki_links(self) -> List[str]:
        """Find all [[...]] references in body text."""
        return WIKI_LINK_PATTERN.findall(self._body)

    def find_relationship_targets(self) -> List[str]:
        """Extract relationship target IDs (``urn:mif:`` prefix stripped).

        Reads the frontmatter ``relationships`` array, MIF 1.4.1 markdown
        links in the body ``## Relationships`` section, and legacy
        ``[[wiki-link]]`` references anywhere in the file.
        """
        targets: List[str] = []
        rels = self.get("relationships")
        if isinstance(rels, list):
            for rel in rels:
                if isinstance(rel, dict):
                    tid = target_ref(rel.get("target"))
                    if tid and tid not in targets:
                        targets.append(tid)
        # MIF 1.4.1 body mirror (markdown links to urn:mif:<uuid>); ordinary
        # prose links in the section are not relationships. Wiki-links below.
        for entry in parse_body_relationships(self._body):
            if entry["form"] != "markdown" or not is_concept_target(entry["target"]):
                continue
            tid = target_ref(entry["target"])
            if tid and tid not in targets:
                targets.append(tid)
        # Also check legacy inline relationship notation in body
        for link in WIKI_LINK_PATTERN.findall(self._raw):
            if link not in targets:
                targets.append(link)
        return targets

    def validate_frontmatter(self) -> List[str]:
        """Return list of validation error messages."""
        errors: List[str] = []
        fm = self._frontmatter
        if not fm:
            errors.append("No frontmatter found")
            return errors

        for field in REQUIRED_FIELDS:
            if field not in fm:
                errors.append(f"Missing required field: {field}")

        # Validate id format
        uid = self.uuid
        if uid and not UUID_PATTERN.match(uid):
            errors.append(f"Invalid UUID format: {uid}")

        # Validate type
        mtype = self.memory_type
        if mtype and mtype not in VALID_TYPES:
            errors.append(f"Invalid type '{mtype}', must be one of: {', '.join(sorted(VALID_TYPES))}")

        # Validate created date
        created = self.get("created")
        if created:
            import datetime as dt_mod

            if isinstance(created, (dt_mod.datetime, dt_mod.date)):
                pass  # PyYAML parsed it as datetime/date - valid
            else:
                created_str = str(created)
                if not ISO_DATE_PATTERN.match(created_str):
                    errors.append(f"Invalid created date format: {created_str}")

        return errors

    def update_field_in_raw(self, key: str, value: str) -> None:
        """Update a top-level frontmatter field in the raw content.

        Uses regex replacement to preserve formatting.
        """
        # Try to replace existing field
        pattern = re.compile(rf"^({re.escape(key)}:\s*)(.+)$", re.MULTILINE)
        if pattern.search(self._fm_block):
            self._fm_block = pattern.sub(rf"\g<1>{value}", self._fm_block, count=1)
        else:
            # Insert before closing ---
            self._fm_block = re.sub(
                r"(---)$",
                f"{key}: {value}\n---",
                self._fm_block,
            )
        self._frontmatter[key] = value
        self._dirty = True

    def update_nested_field(self, keys: List[str], value: str) -> None:
        """Update a nested field like temporal.decay.currentStrength.

        Uses regex to find and replace the leaf key in the raw frontmatter.
        """
        leaf_key = keys[-1]
        pattern = re.compile(rf"^(\s*{re.escape(leaf_key)}:\s*)(.+)$", re.MULTILINE)
        if pattern.search(self._fm_block):
            self._fm_block = pattern.sub(rf"\g<1>{value}", self._fm_block, count=1)
            # Update parsed dict
            obj: Any = self._frontmatter
            for k in keys[:-1]:
                if isinstance(obj, dict):
                    obj = obj.setdefault(k, {})
            if isinstance(obj, dict):
                obj[keys[-1]] = value
            self._dirty = True

    def replace_in_body(self, old: str, new: str) -> int:
        """Replace text in body. Returns number of replacements."""
        count = self._body.count(old)
        if count > 0:
            self._body = self._body.replace(old, new)
            self._dirty = True
        return count

    def replace_in_raw(self, old: str, new: str) -> int:
        """Replace text in entire raw content. Returns number of replacements."""
        count = self._raw.count(old)
        if count > 0:
            self._fm_block = self._fm_block.replace(old, new)
            self._body = self._body.replace(old, new)
            self._dirty = True
        return count

    def save(self) -> None:
        """Write changes back to disk atomically."""
        if not self._dirty:
            return
        new_content = self._fm_block + "\n\n" + self._body + "\n"
        tmp = self.path.with_suffix(".memory.md.tmp")
        try:
            tmp.write_text(new_content)
            tmp.replace(self.path)
            self._dirty = False
        except OSError:
            # Clean up temp file on failure
            if tmp.exists():
                tmp.unlink()
            raise

    def __repr__(self) -> str:
        return f"MemoryFile({self.path.name})"
