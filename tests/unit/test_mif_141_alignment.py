#!/usr/bin/env python3
"""
MIF 1.4.2 alignment: new forms are written, legacy forms are still read.

Covers lib/mif_compat.py, the relationship writer, memory reader, custodian
readers, mnemonic-validate, ontology resolution and the opt-in migration
(lib/mif_migrate.py + tools/mnemonic-migrate-mif). Every migration test runs
against tmp_path fixtures only.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib import mif_compat
from lib.memory_reader import get_memory_metadata
from lib.mif_compat import (
    body_has_relationship,
    find_legacy_keys,
    format_target,
    get_compat,
    get_nested_compat,
    migrate_legacy_keys,
    parse_body_relationships,
    relationship_label,
    same_target,
    target_ref,
    to_kebab,
    upsert_body_relationship,
)
from lib.paths import PathContext, PathResolver, PathScheme
from lib.relationships import add_bidirectional_relationship, add_relationship, is_valid_type, to_pascal, to_token

try:
    import yaml  # noqa: F401

    HAVE_YAML = True
except ImportError:  # CI's test job installs only pytest
    HAVE_YAML = False

needs_yaml = pytest.mark.skipif(not HAVE_YAML, reason="PyYAML not installed")

UUID_A = "11111111-2222-4333-8444-555555555555"
UUID_B = "66666666-7777-4888-9999-000000000000"
UUID_C = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
TOOLS = project_root / "tools"
FIXTURES = project_root / "tests" / "fixtures" / "memories"

LEGACY_MEMORY = f"""---
id: {UUID_A}
type: semantic
namespace: _semantic/decisions
created: 2026-01-23T10:30:00Z
title: "Use PostgreSQL"
confidence: 0.9
half_life: P90D
# a comment that must survive
temporal:
  valid_from: 2026-01-23T00:00:00Z
  recorded_at: 2026-01-23T10:30:00Z
  last_accessed: 2026-01-23T10:30:00Z
provenance:
  source_type: conversation  # legacy value
  agent: claude-opus-4
relationships:
  - type: relates_to
    target: {UUID_B}
    label: "Related caching decision"
citations:
  - type: documentation
    title: "PG docs"
    url: https://www.postgresql.org/docs/
compressed_at: 2026-01-24T10:00:00Z
---

# Use PostgreSQL

Inline [[{UUID_B}]] mention in prose.

## Relationships

- supersedes [[old-choice]]
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _memory(path: Path, uid: str, title: str, extra: str = "", body: str = "Body.\n") -> Path:
    return _write(
        path, f'---\nid: {uid}\ntype: semantic\ncreated: 2026-01-01T00:00:00Z\ntitle: "{title}"\n{extra}---\n\n{body}'
    )


# ---------------------------------------------------------------------------
# lib.mif_compat
# ---------------------------------------------------------------------------


class TestCompatKeys:
    def test_get_compat_prefers_camel_case(self):
        assert get_compat({"validFrom": "new", "valid_from": "old"}, "validFrom") == "new"

    def test_get_compat_falls_back_to_snake_case(self):
        assert get_compat({"valid_from": "old"}, "validFrom") == "old"
        assert get_compat({"compressed_at": "t"}, "compressedAt") == "t"

    def test_get_compat_default_and_non_mapping(self):
        assert get_compat({}, "validFrom", "d") == "d"
        assert get_compat(None, "validFrom", "d") == "d"

    def test_get_nested_compat_mixed_spellings(self):
        fm = {"temporal": {"decay": {"half_life": "P7D"}, "lastAccessed": "x"}}
        assert get_nested_compat(fm, "temporal", "decay", "halfLife") == "P7D"
        assert get_nested_compat(fm, "temporal", "lastAccessed") == "x"
        assert get_nested_compat(fm, "temporal", "missing", default=0) == 0

    def test_find_legacy_keys(self):
        fm = {
            "compressed_at": 1,
            "temporal": {"valid_from": 1, "validUntil": 2, "decay": {"half_life": 1}},
            "provenance": {"source_type": "x"},
            "extensions": {"valid_from": "not ours"},
        }
        found = dict(find_legacy_keys(fm))
        assert found == {
            "compressed_at": "compressedAt",
            "temporal.valid_from": "temporal.validFrom",
            "temporal.decay.half_life": "temporal.decay.halfLife",
            "provenance.source_type": "provenance.sourceType",
        }

    def test_find_legacy_keys_clean_for_new_form(self):
        assert find_legacy_keys({"temporal": {"validFrom": 1}, "compressedAt": 2}) == []

    def test_migrate_legacy_keys_keeps_order_and_reports_conflicts(self):
        fm = {
            "id": 1,
            "compressed_at": 2,
            "title": 3,
            "provenance": {"source_type": "a", "sourceRef": "r", "source_ref": "old"},
        }
        changes, conflicts = migrate_legacy_keys(fm)
        assert list(fm) == ["id", "compressedAt", "title", "provenance"]
        assert fm["provenance"]["sourceType"] == "a"
        # Conflict: camelCase twin exists, legacy key is left for a human
        assert fm["provenance"]["source_ref"] == "old"
        assert fm["provenance"]["sourceRef"] == "r"
        assert "compressed_at -> compressedAt" in changes
        assert any("source_ref" in c for c in conflicts)


class TestCompatRelationships:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("relates_to", "relates-to"),
            ("RelatesTo", "relates-to"),
            ("relates-to", "relates-to"),
            ("SupersededBy", "superseded-by"),
            ("derived_from", "derived-from"),
            ("Uses", "uses"),
            ("farm:BreedsWith", "farm:breeds-with"),
            ("", ""),
        ],
    )
    def test_to_kebab(self, raw, expected):
        assert to_kebab(raw) == expected

    def test_targets(self):
        assert target_ref(f"urn:mif:{UUID_A}") == UUID_A
        assert target_ref({"@id": f"urn:mif:{UUID_A}"}) == UUID_A
        assert target_ref(UUID_A) == UUID_A
        assert target_ref("/semantic/x.md") == "/semantic/x.md"
        assert format_target(UUID_A) == f"urn:mif:{UUID_A}"
        assert format_target(f"urn:mif:{UUID_A}") == f"urn:mif:{UUID_A}"
        assert format_target("/semantic/x.md") == "/semantic/x.md"
        assert format_target("not-a-uuid") == "not-a-uuid"
        assert same_target(UUID_A, f"urn:mif:{UUID_A.upper()}")
        assert not same_target(UUID_A, UUID_B)

    def test_relationship_label_both_forms(self):
        assert relationship_label({"metadata": {"label": "new"}, "label": "old"}) == "new"
        assert relationship_label({"label": "old"}) == "old"
        assert relationship_label({}) is None

    def test_parse_body_relationships_both_forms(self):
        body = (
            "Intro [[not-a-relationship]].\n\n## Relationships\n\n"
            f"- relates-to [Cache]({'urn:mif:' + UUID_B})\n"
            f"- supersedes [[{UUID_C}|Old]]\n"
            "- not a relationship line\n\n## Notes\n\n- derives [[ignored]]\n"
        )
        rels = parse_body_relationships(body)
        assert rels == [
            {"type": "relates-to", "text": "Cache", "target": f"urn:mif:{UUID_B}", "form": "markdown"},
            {"type": "supersedes", "text": "Old", "target": UUID_C, "form": "wiki"},
        ]

    def test_body_has_relationship_matches_legacy_spelling(self):
        body = f"## Relationships\n\n- relates_to [[{UUID_B}]]\n"
        assert body_has_relationship(body, "relates-to", f"urn:mif:{UUID_B}")
        assert not body_has_relationship(body, "supersedes", UUID_B)

    def test_upsert_creates_section(self):
        out = upsert_body_relationship("# T\n\nBody.\n", "RelatesTo", UUID_B, "Cache")
        assert out == f"# T\n\nBody.\n\n## Relationships\n\n- relates-to [Cache](urn:mif:{UUID_B})\n"

    def test_upsert_appends_before_next_heading_and_is_idempotent(self):
        body = f"Body.\n\n## Relationships\n\n- supersedes [Old](urn:mif:{UUID_C})\n\n## Notes\n\nKeep.\n"
        out = upsert_body_relationship(body, "relates-to", UUID_B, "Cache")
        assert f"- supersedes [Old](urn:mif:{UUID_C})\n- relates-to [Cache](urn:mif:{UUID_B})\n\n## Notes" in out
        assert upsert_body_relationship(out, "relates_to", UUID_B, "Cache") == out

    def test_upsert_noop_when_legacy_wiki_line_present(self):
        body = f"## Relationships\n\n- relates-to [[{UUID_B}]]\n"
        assert upsert_body_relationship(body, "relates-to", UUID_B) == body


# ---------------------------------------------------------------------------
# Relationship writer (lib.relationships)
# ---------------------------------------------------------------------------


class TestRelationshipWriter:
    def test_kebab_input_is_valid(self):
        assert is_valid_type("relates-to")
        assert is_valid_type("superseded-by")
        assert not is_valid_type("made-up")
        assert to_pascal("superseded-by") == "SupersededBy"
        assert to_token("SupersededBy") == "superseded-by"

    @needs_yaml
    def test_writes_mif_141_form_with_body_mirror(self, tmp_path):
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A")
        assert add_relationship(str(mem), "RelatesTo", UUID_B, label='Say "hi"', target_title="Cache")
        text = mem.read_text()
        assert "  - type: relates-to\n" in text
        assert f"    target: urn:mif:{UUID_B}\n" in text
        assert '    metadata:\n      label: "Say \\"hi\\""' in text
        assert f"## Relationships\n\n- relates-to [Cache](urn:mif:{UUID_B})\n" in text
        # The written frontmatter is valid YAML with the label intact
        meta = get_memory_metadata(str(mem))
        assert meta["relationships"] == [{"type": "relates-to", "target": f"urn:mif:{UUID_B}", "label": 'Say "hi"'}]

    def test_legacy_entry_counts_as_duplicate(self, tmp_path):
        extra = f"relationships:\n  - type: relates_to\n    target: {UUID_B}\n"
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra)
        before = mem.read_text()
        assert add_relationship(str(mem), "relates-to", f"urn:mif:{UUID_B}") is False
        assert mem.read_text() == before

    def test_new_entry_counts_as_duplicate(self, tmp_path):
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A")
        assert add_relationship(str(mem), "supersedes", UUID_B)
        assert add_relationship(str(mem), "Supersedes", UUID_B) is False

    def test_legacy_body_wiki_line_is_not_duplicated(self, tmp_path):
        mem = _memory(
            tmp_path / "a.memory.md", UUID_A, "A", body=f"Body.\n\n## Relationships\n\n- relates_to [[{UUID_B}]]\n"
        )
        assert add_relationship(str(mem), "relates-to", UUID_B)
        text = mem.read_text()
        assert text.count(UUID_B) == 2  # frontmatter target + existing legacy body line
        assert f"[[{UUID_B}]]" in text

    def test_bidirectional_uses_titles_and_urns(self, tmp_path):
        a = _memory(tmp_path / "a.memory.md", UUID_A, "Alpha")
        b = _memory(tmp_path / "b.memory.md", UUID_B, "Beta")
        assert add_bidirectional_relationship(str(a), str(b), "derived_from") == (True, True)
        assert f"- derived-from [Beta](urn:mif:{UUID_B})" in a.read_text()
        assert f"- derives [Alpha](urn:mif:{UUID_A})" in b.read_text()


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


class TestReaders:
    def test_memory_reader_regex_fallback_reads_urn_targets(self, monkeypatch, tmp_path):
        import lib.memory_reader as reader

        monkeypatch.setattr(reader, "yaml", None)
        extra = (
            f"relationships:\n  - type: relates-to\n    target: urn:mif:{UUID_B}\n"
            f"  - type: relates_to\n    target: {UUID_C}\n    label: legacy\n"
        )
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra)
        rels = reader.get_memory_metadata(str(mem))["relationships"]
        assert rels[0]["target"] == f"urn:mif:{UUID_B}"
        assert rels[1] == {"type": "relates_to", "target": UUID_C, "label": "legacy"}

    @needs_yaml
    def test_custodian_memory_file_targets_and_compat(self, tmp_path):
        from skills.custodian.lib.memory_file import MemoryFile

        extra = f"temporal:\n  last_accessed: 2026-01-01T00:00:00Z\nrelationships:\n  - type: relates-to\n    target: urn:mif:{UUID_B}\n"
        body = f"Body.\n\n## Relationships\n\n- relates-to [B](urn:mif:{UUID_B})\n- supersedes [C](urn:mif:{UUID_C})\n"
        mem = MemoryFile(_memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra, body=body))
        assert mem.find_relationship_targets() == [UUID_B, UUID_C]
        assert str(mem.get_compat("temporal", "lastAccessed")).startswith("2026-01-01")

    @needs_yaml
    @pytest.mark.parametrize("key", ["lastAccessed", "last_accessed"])
    def test_decay_reads_both_spellings(self, tmp_path, key):
        from skills.custodian.lib.decay import update_decay
        from skills.custodian.lib.report import Report

        half = "halfLife" if key == "lastAccessed" else "half_life"
        extra = f"temporal:\n  {key}: 2020-01-01T00:00:00Z\n  decay:\n    model: exponential\n    {half}: P30D\n    strength: 1.0\n"
        _memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra)
        report = Report("test")
        update_decay([tmp_path], report, dry_run=True)
        assert any("Strength: 1.00 ->" in f.message for f in report.findings)

    @needs_yaml
    def test_ensure_bidirectional_accepts_legacy_back_ref(self, tmp_path):
        from skills.custodian.lib.link_checker import LinkIndex, ensure_bidirectional
        from skills.custodian.lib.report import Report

        _memory(
            tmp_path / "a.memory.md",
            UUID_A,
            "A",
            extra=f"relationships:\n  - type: supersedes\n    target: urn:mif:{UUID_B}\n",
        )
        _memory(
            tmp_path / "b.memory.md",
            UUID_B,
            "B",
            extra=f"relationships:\n  - type: superseded_by\n    target: {UUID_A}\n",
        )
        index = LinkIndex()
        index.build([tmp_path])
        assert ensure_bidirectional(index, Report("test"), fix=False) == 0

    @needs_yaml
    def test_ensure_bidirectional_fix_writes_new_form(self, tmp_path):
        from skills.custodian.lib.link_checker import LinkIndex, ensure_bidirectional
        from skills.custodian.lib.report import Report

        _memory(
            tmp_path / "a.memory.md",
            UUID_A,
            "Alpha",
            extra=f"relationships:\n  - type: Supersedes\n    target: {UUID_B}\n",
        )
        b = _memory(tmp_path / "b.memory.md", UUID_B, "Beta")
        index = LinkIndex()
        index.build([tmp_path])
        assert ensure_bidirectional(index, Report("test"), fix=True) == 1
        text = b.read_text()
        assert f"  - type: superseded-by\n    target: urn:mif:{UUID_A}" in text
        assert f"- superseded-by [Alpha](urn:mif:{UUID_A})" in text

    @needs_yaml
    def test_custodian_validator_reads_both_source_type_spellings(self, tmp_path):
        from skills.custodian.lib.report import Report
        from skills.custodian.lib.validators import validate_memories, validate_relationships

        _memory(tmp_path / "a.memory.md", UUID_A, "A", extra="provenance:\n  source_type: bogus\n")
        _memory(
            tmp_path / "b.memory.md",
            UUID_B,
            "B",
            extra=f"provenance:\n  sourceType: user_explicit\nrelationships:\n  - type: relates-to\n    target: urn:mif:{UUID_A}\n",
        )
        report = Report("test")
        validate_memories([tmp_path], report)
        assert validate_relationships([tmp_path], report) == 0
        messages = [f.message for f in report.findings]
        assert any("Unknown provenance sourceType: bogus" in m for m in messages)
        assert any("Legacy key(s) provenance.source_type" in m for m in messages)
        assert not any("user_explicit" in m for m in messages)


# ---------------------------------------------------------------------------
# mnemonic-validate
# ---------------------------------------------------------------------------


def _validate(*args):
    result = subprocess.run(
        [sys.executable, str(TOOLS / "mnemonic-validate"), *args, "--format", "json"], capture_output=True, text=True
    )
    return result, json.loads(result.stdout)


@needs_yaml
class TestValidatorTool:
    def test_new_form_fixture_is_clean(self):
        result, out = _validate(str(FIXTURES / "valid-mif-1-4-1.memory.md"))
        assert result.returncode == 0
        assert out["summary"]["errors"] == 0
        assert out["summary"]["warnings"] == 0

    def test_legacy_file_is_valid_with_warnings(self, tmp_path):
        mem = _write(tmp_path / "legacy.memory.md", LEGACY_MEMORY)
        result, out = _validate(str(mem))
        assert result.returncode == 0
        assert out["summary"]["errors"] == 0
        fields = {w["field"] for r in out["results"] for w in r["warnings"]}
        for expected in (
            "compressed_at",
            "temporal.valid_from",
            "provenance.source_type",
            "provenance.sourceType",
            "relationships[0].type",
            "relationships[0].label",
            "relationships[0]",
            "citations[0].type",
            "body",
        ):
            assert expected in fields, expected

    def test_invalid_compressed_at_is_an_error_in_either_spelling(self, tmp_path):
        for key in ("compressedAt", "compressed_at"):
            mem = _write(
                tmp_path / f"{key}.memory.md",
                f'---\nid: {UUID_A}\ntype: semantic\nnamespace: decisions/project\ncreated: 2026-01-01T00:00:00Z\ntitle: "T"\n{key}: yesterday\n---\n\nBody.\n',
            )
            result, out = _validate(str(mem))
            assert out["summary"]["errors"] == 1, key


# ---------------------------------------------------------------------------
# Ontology resolution (MIF 1.4.2 section 10.8.5)
# ---------------------------------------------------------------------------


class TestOntologyResolution:
    def _resolver(self, tmp_path, scheme):
        home = tmp_path / "home"
        project = tmp_path / "project"
        ctx = PathContext(
            org="org",
            project="proj",
            home_dir=home,
            project_dir=project,
            memory_root=home / ".claude" / "mnemonic",
            scheme=scheme,
        )
        return PathResolver(ctx), home, project

    @pytest.mark.parametrize("scheme", [PathScheme.LEGACY, PathScheme.V2])
    def test_mif_dirs_precede_legacy_locations(self, tmp_path, scheme):
        resolver, home, project = self._resolver(tmp_path, scheme)
        (project / ".mif" / "ontologies" / "domain").mkdir(parents=True)
        (home / ".mif" / "ontologies").mkdir(parents=True)
        p1 = _write(project / ".mif" / "ontologies" / "ontology.yaml", "ontology: {id: p}\n")
        p2 = _write(project / ".mif" / "ontologies" / "domain" / "se.ontology.yaml", "ontology: {id: se}\n")
        _write(project / ".mif" / "ontologies" / "notes.yaml", "ignored: true\n")
        u1 = _write(home / ".mif" / "ontologies" / "user.ontology.yaml", "ontology: {id: u}\n")

        paths = resolver.get_ontology_paths()
        assert paths[:2] == [p1, p2]
        assert paths[3] == u1
        legacy_project = paths[2]
        assert legacy_project.name == "ontology.yaml" and ".mif" not in legacy_project.parts
        assert ".mif" not in paths[4].parts
        assert len(paths) == 5

    def test_legacy_only_unchanged(self, tmp_path):
        resolver, home, project = self._resolver(tmp_path, PathScheme.LEGACY)
        assert resolver.get_ontology_paths() == [
            project / ".claude" / "mnemonic" / "ontology.yaml",
            home / ".claude" / "mnemonic" / "ontology.yaml",
        ]

    @needs_yaml
    def test_loader_prefers_project_mif_dir(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(project_root / "skills" / "ontology" / "lib"))
        from skills.ontology.lib.ontology_loader import OntologyLoader

        project = tmp_path / "project"
        home = tmp_path / "home"
        (project / ".mif" / "ontologies").mkdir(parents=True)
        (project / ".claude" / "mnemonic").mkdir(parents=True)
        home.mkdir()
        _write(
            project / ".mif" / "ontologies" / "new.ontology.yaml",
            "ontology:\n  id: from-mif-dir\n  version: 1.0.0\n",
        )
        _write(
            project / ".claude" / "mnemonic" / "ontology.yaml",
            "ontology:\n  id: from-legacy\n  version: 1.0.0\n",
        )
        monkeypatch.chdir(project)
        monkeypatch.setenv("HOME", str(home))
        loaded = OntologyLoader(plugin_root=project_root / "skills" / "ontology").load_project_ontology("org", "proj")
        assert loaded is not None and loaded.id == "from-mif-dir"

    def test_bundled_ontologies_validate_against_vendored_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        yaml = pytest.importorskip("yaml")
        fallback = project_root / "skills" / "ontology" / "fallback"
        schema = json.loads((fallback / "schema" / "ontology" / "ontology.schema.json").read_text())
        assert schema["$id"] == "https://mif-spec.dev/schema/ontology/ontology.schema.json"
        validator = jsonschema.Draft202012Validator(schema)
        for path in sorted((fallback / "ontologies").rglob("*.ontology.yaml")):
            errors = list(validator.iter_errors(yaml.safe_load(path.read_text())))
            assert errors == [], (path.name, [e.message for e in errors])


# ---------------------------------------------------------------------------
# Opt-in migration (lib.mif_migrate / tools/mnemonic-migrate-mif)
# ---------------------------------------------------------------------------


@pytest.fixture
def legacy_store(tmp_path):
    pytest.importorskip("ruamel.yaml")
    store = tmp_path / "store"
    store.mkdir()
    _write(store / "decision.memory.md", LEGACY_MEMORY)
    _memory(store / "cache.memory.md", UUID_B, "Use Redis")
    _memory(store / "old-choice.memory.md", UUID_C, "Use SQLite")
    return store


class TestMigration:
    def test_plan_does_not_write(self, legacy_store):
        from lib.mif_migrate import build_title_index, find_memory_files, plan_file

        target = legacy_store / "decision.memory.md"
        before = target.read_bytes()
        files, _ = find_memory_files([legacy_store])
        plan = plan_file(target, build_title_index(files))
        assert plan.changed
        assert target.read_bytes() == before
        assert not list(legacy_store.glob("*.bak"))

    def test_apply_rewrites_backs_up_and_is_idempotent(self, legacy_store):
        from lib.mif_migrate import BACKUP_SUFFIX, apply_plan, build_title_index, find_memory_files, plan_file

        target = legacy_store / "decision.memory.md"
        files, _ = find_memory_files([legacy_store])
        index = build_title_index(files)
        plan = plan_file(target, index)
        backup = apply_plan(plan)
        assert backup == target.with_name(target.name + BACKUP_SUFFIX)
        assert backup.read_text() == LEGACY_MEMORY

        text = target.read_text()
        meta = get_memory_metadata(str(target))
        assert meta["id"] == UUID_A
        assert "# a comment that must survive" in text
        assert "source_type" not in text
        assert "  sourceType: conversation" in text and "# legacy value" in text  # EOL comment kept
        assert "compressedAt: 2026-01-24T10:00:00Z" in text
        assert "  validFrom: 2026-01-23T00:00:00Z" in text
        assert "    halfLife: P90D" in text
        assert "  confidence: 0.9" in text and "\nconfidence:" not in text
        assert f"  - type: relates-to\n    target: urn:mif:{UUID_B}\n    metadata:\n      label:" in text
        assert f"  - type: supersedes\n    target: urn:mif:{UUID_C}" in text
        assert "citationType: documentation" in text
        assert f"- supersedes [Use SQLite](urn:mif:{UUID_C})" in text
        assert f"- relates-to [Use Redis](urn:mif:{UUID_B})" in text
        assert f"Inline [[{UUID_B}]] mention in prose." in text  # prose untouched
        assert any("citationRole" in n for n in plan.notes)
        assert any("sourceType 'conversation'" in n for n in plan.notes)

        again = plan_file(target, build_title_index(files))
        assert not again.changed

        result, out = _validate(str(target))
        assert out["summary"]["errors"] == 0
        fields = {w["field"] for r in out["results"] for w in r["warnings"]}
        assert fields <= {"provenance.sourceType", "citations[0].citationRole"}

    def test_unresolvable_wiki_link_is_kept(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file

        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", body="## Relationships\n\n- relates-to [[nowhere]]\n")
        plan = plan_file(mem, {})
        assert not plan.changed
        assert any("nowhere" in n for n in plan.notes)

    def test_unparseable_and_frontmatterless_files_error(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file

        bad = _write(tmp_path / "bad.memory.md", "---\nid: [unclosed\n---\n\nBody.\n")
        none = _write(tmp_path / "none.memory.md", "Just text.\n")
        assert plan_file(bad).error
        assert plan_file(none).error == "no YAML frontmatter"

    def test_new_form_file_untouched(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file

        src = FIXTURES / "valid-mif-1-4-1.memory.md"
        copy = _write(tmp_path / src.name, src.read_text())
        assert not plan_file(copy).changed

    def test_symlinks_skipped(self, tmp_path):
        from lib.mif_migrate import find_memory_files

        real = _memory(tmp_path / "real.memory.md", UUID_A, "A")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "link.memory.md").symlink_to(real)
        files, skipped = find_memory_files([tmp_path])
        assert files == [real]
        assert any("symlink" in s for s in skipped)

    def test_cli_dry_run_writes_nothing(self, legacy_store):
        before = {p.name: p.read_bytes() for p in legacy_store.iterdir()}
        result = subprocess.run(
            [sys.executable, str(TOOLS / "mnemonic-migrate-mif"), str(legacy_store), "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["mode"] == "dry-run"
        assert report["changed"] == 1
        assert {p.name: p.read_bytes() for p in legacy_store.iterdir()} == before

    def test_cli_apply_then_noop(self, legacy_store):
        cmd = [sys.executable, str(TOOLS / "mnemonic-migrate-mif"), str(legacy_store)]
        first = subprocess.run(cmd + ["--apply"], capture_output=True, text=True)
        assert first.returncode == 0, first.stderr
        assert (legacy_store / "decision.memory.md.pre-mif-1.4.1.bak").exists()
        second = subprocess.run(cmd + ["--json"], capture_output=True, text=True)
        assert json.loads(second.stdout)["changed"] == 0

    def test_cli_rejects_no_backup_without_apply(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "mnemonic-migrate-mif"), str(tmp_path), "--no-backup"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2


def test_module_is_stdlib_only():
    """lib/mif_compat.py is imported by hooks; it must not need third-party packages."""
    source = Path(mif_compat.__file__).read_text()
    for name in ("yaml", "ruamel", "jsonschema"):
        assert f"import {name}" not in source


# ---------------------------------------------------------------------------
# Review follow-ups (PR #45)
# ---------------------------------------------------------------------------


class TestReviewFollowUps:
    def test_dict_target_is_not_duplicated_by_migration(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file

        extra = f'relationships:\n  - type: relates_to\n    target: {{"@id": "urn:mif:{UUID_B}"}}\n'
        body = f"Body.\n\n## Relationships\n\n- relates-to [B](urn:mif:{UUID_B})\n"
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra, body=body)
        plan = plan_file(mem)
        assert not any("(from body)" in c for c in plan.changes)
        assert f"target: urn:mif:{UUID_B}" in plan.new_text
        assert plan.new_text.count(f"urn:mif:{UUID_B}") == 2  # one frontmatter entry, one body line

    def test_prose_links_are_not_relationships(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file
        from skills.custodian.lib.memory_file import MemoryFile

        body = "Body.\n\n## Relationships\n\n- Related [RFC](https://example.com/rfc)\n"
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", body=body)
        assert not plan_file(mem).changed
        assert MemoryFile(mem).find_relationship_targets() == []

    def test_moved_first_key_keeps_its_comment(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        from lib.mif_migrate import plan_file

        mem = _write(
            tmp_path / "a.memory.md",
            f'---\nconfidence: 0.9  # how sure\n# about the title\ntitle: "x"\nid: {UUID_A}\n---\n\nBody\n',
        )
        text = plan_file(mem).new_text
        assert "provenance:\n  # how sure\n  confidence: 0.9" in text
        assert '# about the title\ntitle: "x"' in text

    def test_crlf_and_permissions_preserved(self, tmp_path):
        pytest.importorskip("ruamel.yaml")
        import os
        import stat

        from lib.mif_migrate import apply_plan, plan_file

        mem = tmp_path / "a.memory.md"
        mem.write_bytes(
            f"---\r\nid: {UUID_A}\r\ntitle: A\r\nrelationships:\r\n  - type: relates_to\r\n    target: {UUID_B}\r\n---\r\n\r\nBody.\r\n".encode()
        )
        os.chmod(mem, 0o600)
        apply_plan(plan_file(mem))
        data = mem.read_bytes()
        assert b"relates-to" in data
        assert b"\n" not in data.replace(b"\r\n", b"")  # every newline is still CRLF
        assert stat.S_IMODE(mem.stat().st_mode) == 0o600

    def test_cli_reports_write_failure_and_continues(self, legacy_store):
        import os

        if os.geteuid() == 0:
            pytest.skip("root ignores directory permissions")
        os.chmod(legacy_store, 0o500)  # files readable, directory not writable
        try:
            result = subprocess.run(
                [sys.executable, str(TOOLS / "mnemonic-migrate-mif"), str(legacy_store), "--apply", "--json"],
                capture_output=True,
                text=True,
            )
        finally:
            os.chmod(legacy_store, 0o700)
        assert result.returncode == 1
        report = json.loads(result.stdout)
        assert any("write failed" in (f["error"] or "") for f in report["files"])
        assert (legacy_store / "decision.memory.md").read_text() == LEGACY_MEMORY

    @needs_yaml
    def test_decay_does_not_compound(self, tmp_path):
        from skills.custodian.lib.decay import update_decay
        from skills.custodian.lib.memory_file import MemoryFile
        from skills.custodian.lib.report import Report

        extra = "temporal:\n  lastAccessed: 2020-01-01T00:00:00Z\n  decay:\n    model: linear\n    halfLife: P100000D\n    strength: 1.0\n"
        mem = _memory(tmp_path / "a.memory.md", UUID_A, "A", extra=extra)
        update_decay([tmp_path], Report("test"))
        first = float(MemoryFile(mem).get_nested("temporal", "decay", "strength"))
        update_decay([tmp_path], Report("test"))
        second = float(MemoryFile(mem).get_nested("temporal", "decay", "strength"))
        assert first < 1.0
        assert second == first

    @needs_yaml
    def test_ensure_bidirectional_handles_jsonld_target(self, tmp_path):
        from skills.custodian.lib.link_checker import LinkIndex, ensure_bidirectional
        from skills.custodian.lib.report import Report

        _memory(
            tmp_path / "a.memory.md",
            UUID_A,
            "A",
            extra=f'relationships:\n  - type: relates-to\n    target: {{"@id": "urn:mif:{UUID_B}"}}\n',
        )
        _memory(tmp_path / "b.memory.md", UUID_B, "B")
        index = LinkIndex()
        index.build([tmp_path])
        assert ensure_bidirectional(index, Report("test"), fix=False) == 1

    @needs_yaml
    def test_validator_dict_target_and_top_level_legacy_fields(self, tmp_path):
        mem = _write(
            tmp_path / "a.memory.md",
            f'---\nid: {UUID_A}\ntype: semantic\nnamespace: decisions/project\ncreated: 2026-01-01T00:00:00Z\ntitle: "T"\n'
            f'confidence: 0.9\nrelationships:\n  - type: relates-to\n    target: {{"@id": "urn:mif:{UUID_B}"}}\n---\n\n'
            f"Body.\n\n## Relationships\n\n- relates-to [B](urn:mif:{UUID_B})\n",
        )
        _, out = _validate(str(mem))
        fields = {w["field"] for r in out["results"] for w in r["warnings"]}
        assert "relationships[0]" not in fields
        assert "confidence" in fields

    @needs_yaml
    def test_custodian_merges_all_ontology_files(self, tmp_path):
        from skills.custodian.lib.report import Report
        from skills.custodian.lib.validators import load_ontology, validate_relationships

        a = _write(tmp_path / "a.ontology.yaml", "ontology: {id: a}\nrelationships:\n  depends_on: {}\n")
        b = _write(tmp_path / "b.ontology.yaml", "ontology: {id: b}\nrelationships:\n  caused_by: {}\n")
        legacy = _write(tmp_path / "ontology.yaml", "ontology: {id: legacy}\nrelationships:\n  resolves: {}\n")
        data = load_ontology([a, b, legacy, tmp_path / "missing.yaml"])
        assert data["ontology"]["id"] == "a"
        assert set(data["relationships"]) == {"depends_on", "caused_by", "resolves"}

        store = tmp_path / "store"
        store.mkdir()
        _memory(
            store / "m.memory.md",
            UUID_A,
            "M",
            extra=f"relationships:\n  - type: caused-by\n    target: urn:mif:{UUID_B}\n  - type: resolves\n    target: urn:mif:{UUID_C}\n",
        )
        assert validate_relationships([store], Report("test"), data) == 0

    @needs_yaml
    def test_loader_returns_every_applicable_ontology(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(project_root / "skills" / "ontology" / "lib"))
        from skills.ontology.lib.ontology_loader import OntologyLoader

        project = tmp_path / "project"
        home = tmp_path / "home"
        (project / ".mif" / "ontologies").mkdir(parents=True)
        (project / ".claude" / "mnemonic").mkdir(parents=True)
        (home / ".mif" / "ontologies").mkdir(parents=True)
        for path, oid in (
            (project / ".mif" / "ontologies" / "a.ontology.yaml", "proj-a"),
            (project / ".mif" / "ontologies" / "b.ontology.yaml", "proj-b"),
            (project / ".claude" / "mnemonic" / "ontology.yaml", "proj-legacy"),
            (home / ".mif" / "ontologies" / "u.ontology.yaml", "user-mif"),
        ):
            _write(path, f"ontology:\n  id: {oid}\n  version: 1.0.0\n")
        monkeypatch.chdir(project)
        monkeypatch.setenv("HOME", str(home))
        loader = OntologyLoader(plugin_root=project_root / "skills" / "ontology")
        ids = [o.id for o in loader.load_project_ontologies("org", "proj")]
        assert ids == ["proj-a", "proj-b", "proj-legacy", "user-mif"]
        assert loader.load_project_ontology("org", "proj").id == "proj-a"

    def test_ontology_file_helpers_agree(self, tmp_path):
        sys.path.insert(0, str(project_root / "skills" / "ontology" / "lib"))
        from lib.paths import mif_ontology_files
        from skills.ontology.lib.ontology_loader import _mif_ontology_files

        (tmp_path / "x").mkdir()
        for rel in ("ontology.yaml", "a.ontology.yaml", "x/b.ontology.yaml", "notes.yaml"):
            _write(tmp_path / rel, "ontology: {id: t}\n")
        assert mif_ontology_files(tmp_path) == _mif_ontology_files(tmp_path)
        assert [p.name for p in mif_ontology_files(tmp_path)] == ["ontology.yaml", "a.ontology.yaml", "b.ontology.yaml"]

    def test_merge_ontologies_precedence(self):
        from lib.mif_compat import merge_ontologies

        high = {"ontology": {"id": "hi"}, "entity_types": [{"name": "x", "base": "semantic"}], "traits": {"t": 1}}
        low = {
            "ontology": {"id": "lo", "version": "2"},
            "entity_types": [{"name": "x", "base": "episodic"}, {"name": "y"}],
        }
        merged = merge_ontologies([high, low])
        assert merged["ontology"] == {"id": "hi", "version": "2"}
        assert merged["entity_types"] == [{"name": "x", "base": "semantic"}, {"name": "y"}]
        assert high["entity_types"] == [{"name": "x", "base": "semantic"}]  # inputs untouched
