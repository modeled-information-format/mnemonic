#!/usr/bin/env python3
"""
Unit tests for lib/relationships.py — type registry, inverse mapping,
conversion helpers, and updated bidirectional linking.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.relationships import (
    RECIPROCAL_TYPES,
    REL_DERIVED_FROM,
    REL_RELATES_TO,
    REL_SUPERSEDES,
    RELATIONSHIP_TYPES,
    add_bidirectional_relationship,
    get_all_valid_types,
    get_inverse,
    is_symmetric,
    is_valid_type,
    to_pascal,
    to_snake,
)


class TestRelationshipTypes:
    """Test the canonical RELATIONSHIP_TYPES registry."""

    def test_nine_core_types_defined(self):
        """MIF spec defines exactly 9 core relationship types."""
        assert len(RELATIONSHIP_TYPES) == 9

    def test_all_types_have_inverse(self):
        """Every type must have an inverse defined."""
        for name, meta in RELATIONSHIP_TYPES.items():
            assert "inverse" in meta, f"{name} missing inverse"
            assert isinstance(meta["inverse"], str)

    def test_all_types_have_symmetry_flag(self):
        """Every type must have a symmetric flag."""
        for name, meta in RELATIONSHIP_TYPES.items():
            assert "symmetric" in meta, f"{name} missing symmetric"
            assert isinstance(meta["symmetric"], bool)

    def test_symmetric_types_are_self_inverse(self):
        """Symmetric types must have inverse == themselves."""
        for name, meta in RELATIONSHIP_TYPES.items():
            if meta["symmetric"]:
                assert meta["inverse"] == name, f"{name} is symmetric but inverse is {meta['inverse']}"

    def test_expected_types_present(self):
        expected = {
            "RelatesTo",
            "DerivedFrom",
            "Supersedes",
            "ConflictsWith",
            "PartOf",
            "Implements",
            "Uses",
            "Created",
            "MentionedIn",
        }
        assert set(RELATIONSHIP_TYPES.keys()) == expected


class TestToPascal:
    """Test to_pascal() conversion."""

    def test_relates_to(self):
        assert to_pascal("relates_to") == "RelatesTo"

    def test_supersedes(self):
        assert to_pascal("supersedes") == "Supersedes"

    def test_derived_from(self):
        assert to_pascal("derived_from") == "DerivedFrom"

    def test_superseded_by(self):
        assert to_pascal("superseded_by") == "SupersededBy"

    def test_conflicts_with(self):
        assert to_pascal("conflicts_with") == "ConflictsWith"

    def test_already_pascal(self):
        assert to_pascal("RelatesTo") == "RelatesTo"

    def test_part_of(self):
        assert to_pascal("part_of") == "PartOf"

    def test_implemented_by(self):
        assert to_pascal("implemented_by") == "ImplementedBy"

    def test_mentioned_in(self):
        assert to_pascal("mentioned_in") == "MentionedIn"


class TestToSnake:
    """Test to_snake() conversion."""

    def test_relates_to(self):
        assert to_snake("RelatesTo") == "relates_to"

    def test_supersedes(self):
        assert to_snake("Supersedes") == "supersedes"

    def test_derived_from(self):
        assert to_snake("DerivedFrom") == "derived_from"

    def test_superseded_by(self):
        assert to_snake("SupersededBy") == "superseded_by"

    def test_already_snake(self):
        assert to_snake("relates_to") == "relates_to"

    def test_contains(self):
        assert to_snake("Contains") == "contains"

    def test_mentions(self):
        assert to_snake("Mentions") == "mentions"


class TestGetInverse:
    """Test get_inverse() — proper inverse mapping."""

    def test_supersedes_inverse(self):
        assert get_inverse("Supersedes") == "SupersededBy"

    def test_superseded_by_inverse(self):
        assert get_inverse("SupersededBy") == "Supersedes"

    def test_derived_from_inverse(self):
        assert get_inverse("DerivedFrom") == "Derives"

    def test_derives_inverse(self):
        assert get_inverse("Derives") == "DerivedFrom"

    def test_relates_to_symmetric(self):
        assert get_inverse("RelatesTo") == "RelatesTo"

    def test_conflicts_with_symmetric(self):
        assert get_inverse("ConflictsWith") == "ConflictsWith"

    def test_part_of_inverse(self):
        assert get_inverse("PartOf") == "Contains"

    def test_contains_inverse(self):
        assert get_inverse("Contains") == "PartOf"

    def test_implements_inverse(self):
        assert get_inverse("Implements") == "ImplementedBy"

    def test_uses_inverse(self):
        assert get_inverse("Uses") == "UsedBy"

    def test_created_inverse(self):
        assert get_inverse("Created") == "CreatedBy"

    def test_mentioned_in_inverse(self):
        assert get_inverse("MentionedIn") == "Mentions"

    def test_snake_case_input(self):
        """get_inverse accepts snake_case and returns PascalCase."""
        assert get_inverse("supersedes") == "SupersededBy"

    def test_snake_case_derived_from(self):
        assert get_inverse("derived_from") == "Derives"

    def test_unknown_type_defaults_to_relates_to(self):
        assert get_inverse("FooBar") == "RelatesTo"


class TestIsValidType:
    """Test is_valid_type() — accepts both naming conventions."""

    def test_pascal_forward_types(self):
        for name in RELATIONSHIP_TYPES:
            assert is_valid_type(name), f"{name} should be valid"

    def test_pascal_inverse_types(self):
        for meta in RELATIONSHIP_TYPES.values():
            assert is_valid_type(meta["inverse"]), f"{meta['inverse']} should be valid"

    def test_snake_case_types(self):
        assert is_valid_type("relates_to")
        assert is_valid_type("supersedes")
        assert is_valid_type("derived_from")
        assert is_valid_type("superseded_by")
        assert is_valid_type("conflicts_with")
        assert is_valid_type("part_of")
        assert is_valid_type("contains")
        assert is_valid_type("implements")
        assert is_valid_type("implemented_by")
        assert is_valid_type("uses")
        assert is_valid_type("used_by")
        assert is_valid_type("created")
        assert is_valid_type("created_by")
        assert is_valid_type("mentioned_in")
        assert is_valid_type("mentions")

    def test_invalid_type(self):
        assert not is_valid_type("FooBar")
        assert not is_valid_type("unknown")
        assert not is_valid_type("")


class TestIsSymmetric:
    """Test is_symmetric()."""

    def test_relates_to_symmetric(self):
        assert is_symmetric("RelatesTo")
        assert is_symmetric("relates_to")

    def test_conflicts_with_symmetric(self):
        assert is_symmetric("ConflictsWith")

    def test_supersedes_not_symmetric(self):
        assert not is_symmetric("Supersedes")

    def test_derived_from_not_symmetric(self):
        assert not is_symmetric("DerivedFrom")


class TestGetAllValidTypes:
    """Test get_all_valid_types()."""

    def test_returns_set(self):
        result = get_all_valid_types()
        assert isinstance(result, set)

    def test_includes_forward_and_inverse(self):
        result = get_all_valid_types()
        assert "Supersedes" in result
        assert "SupersededBy" in result
        assert "DerivedFrom" in result
        assert "Derives" in result
        assert "RelatesTo" in result

    def test_count(self):
        """9 forward + unique inverses. Some inverses are same as forward (symmetric)."""
        result = get_all_valid_types()
        # RelatesTo and ConflictsWith are symmetric (same inverse)
        # So 9 forward + 7 unique inverses = 16 unique types
        assert len(result) == 16


class TestReciprocalTypesBackwardCompat:
    """Test that RECIPROCAL_TYPES still works for backward compatibility."""

    def test_relates_to_symmetric(self):
        assert RECIPROCAL_TYPES[REL_RELATES_TO] == REL_RELATES_TO

    def test_supersedes_now_uses_proper_inverse(self):
        """RECIPROCAL_TYPES[supersedes] should now be superseded_by."""
        assert RECIPROCAL_TYPES[REL_SUPERSEDES] == "superseded_by"

    def test_derived_from_now_uses_proper_inverse(self):
        """RECIPROCAL_TYPES[derived_from] should now be derives."""
        assert RECIPROCAL_TYPES[REL_DERIVED_FROM] == "derives"


class TestBidirectionalRelationshipProperInverse:
    """Test add_bidirectional_relationship uses proper inverse types."""

    def test_supersedes_creates_superseded_by_backlink(self, tmp_path):
        """When A supersedes B, B should get superseded_by (not relates_to)."""
        source = tmp_path / "source.memory.md"
        target = tmp_path / "target.memory.md"
        source.write_text('---\nid: aaa-111\ntitle: "Source"\n---\n\nBody.\n')
        target.write_text('---\nid: bbb-222\ntitle: "Target"\n---\n\nBody.\n')

        fwd, rev = add_bidirectional_relationship(str(source), str(target), REL_SUPERSEDES, label="Newer version")

        assert fwd is True
        assert rev is True

        source_content = source.read_text()
        target_content = target.read_text()

        # Forward: supersedes
        assert "type: supersedes" in source_content
        assert "target: bbb-222" in source_content

        # Reverse: superseded-by (proper inverse, written as the MIF 1.4.1 token)
        assert "type: superseded-by" in target_content
        assert "target: aaa-111" in target_content

    def test_derived_from_creates_derives_backlink(self, tmp_path):
        """When A derived_from B, B should get derives (not relates_to)."""
        source = tmp_path / "source.memory.md"
        target = tmp_path / "target.memory.md"
        source.write_text('---\nid: aaa-111\ntitle: "Source"\n---\n\nBody.\n')
        target.write_text('---\nid: bbb-222\ntitle: "Target"\n---\n\nBody.\n')

        fwd, rev = add_bidirectional_relationship(str(source), str(target), REL_DERIVED_FROM)

        assert fwd is True
        assert rev is True

        target_content = target.read_text()
        assert "type: derives" in target_content

    def test_relates_to_still_symmetric(self, tmp_path):
        """relates_to is symmetric: both sides get relates-to."""
        source = tmp_path / "source.memory.md"
        target = tmp_path / "target.memory.md"
        source.write_text('---\nid: aaa-111\ntitle: "Source"\n---\n\nBody.\n')
        target.write_text('---\nid: bbb-222\ntitle: "Target"\n---\n\nBody.\n')

        fwd, rev = add_bidirectional_relationship(str(source), str(target), REL_RELATES_TO)

        assert fwd is True
        assert rev is True

        source_content = source.read_text()
        target_content = target.read_text()
        assert "type: relates-to" in source_content
        assert "type: relates-to" in target_content

    def test_pascal_case_input(self, tmp_path):
        """PascalCase input produces the kebab-case inverse token."""
        source = tmp_path / "source.memory.md"
        target = tmp_path / "target.memory.md"
        source.write_text('---\nid: aaa-111\ntitle: "Source"\n---\n\nBody.\n')
        target.write_text('---\nid: bbb-222\ntitle: "Target"\n---\n\nBody.\n')

        fwd, rev = add_bidirectional_relationship(str(source), str(target), "Supersedes")

        assert fwd is True
        assert rev is True

        target_content = target.read_text()
        # Any input spelling is written as the MIF 1.4.1 kebab-case token
        assert "type: superseded-by" in target_content
