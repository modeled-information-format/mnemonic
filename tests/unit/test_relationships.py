#!/usr/bin/env python3
"""
Unit tests for hooks/post_tool_use.py relationship suggestion functions
and lib/search.py relationship type inference.

Tests the updated get_relationship_suggestions() which uses scored search
and relationship type inference with PascalCase return values.
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path for hooks imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from hooks.post_tool_use import get_relationship_suggestions
from lib.search import infer_relationship_type


class TestGetRelationshipSuggestions:
    """Test get_relationship_suggestions() function."""

    @patch("hooks.post_tool_use.find_related_memories_scored")
    @patch("hooks.post_tool_use.extract_keywords_from_path")
    @patch("hooks.post_tool_use.infer_relationship_type")
    def test_suggestions_success(self, mock_infer, mock_keywords, mock_search):
        """Test successful relationship suggestions with IDs and types."""
        ontology_data = {
            "relationships": {
                "relates_to": {"description": "Generic relationship"},
                "supersedes": {"description": "Replaces older item"},
            }
        }

        mock_keywords.return_value = "auth handler"
        mock_search.return_value = [
            {
                "id": "a5e46807-6883-4fb2-be45-09872ae1a994",
                "title": "JWT Authentication Decision",
                "path": "/path/to/jwt.memory.md",
                "namespace": "_semantic/decisions",
                "tags": ["auth"],
                "score": 65,
                "match_reasons": ["Same namespace"],
            }
        ]
        mock_infer.return_value = "RelatesTo"

        result = get_relationship_suggestions(ontology_data, "/src/auth_handler.py", "_semantic/decisions")

        assert result != ""
        # Suggestions use the MIF 1.4.1 kebab-case token agents should write
        assert "[relates-to]" in result
        assert "JWT Authentication Decision" in result
        assert "a5e46807-688" in result
        assert "score: 65" in result

    @patch("hooks.post_tool_use.extract_keywords_from_path")
    def test_no_relationships_in_ontology(self, mock_keywords):
        """Test when ontology has no relationships."""
        result = get_relationship_suggestions({}, "/src/file.py", "_semantic/decisions")
        assert result == ""

    @patch("hooks.post_tool_use.extract_keywords_from_path")
    def test_empty_relationships(self, mock_keywords):
        """Test when ontology has empty relationships dict."""
        result = get_relationship_suggestions({"relationships": {}}, "/src/file.py", "_semantic/decisions")
        assert result == ""

    @patch("hooks.post_tool_use.find_related_memories_scored")
    @patch("hooks.post_tool_use.extract_keywords_from_path")
    def test_no_path_keywords(self, mock_keywords, mock_search):
        """Test when file path yields no keywords."""
        ontology_data = {"relationships": {"relates_to": {}}}
        mock_keywords.return_value = ""

        result = get_relationship_suggestions(ontology_data, "/a/b.py", "_semantic/decisions")
        assert result == ""

    @patch("hooks.post_tool_use.find_related_memories_scored")
    @patch("hooks.post_tool_use.extract_keywords_from_path")
    def test_no_related_memories(self, mock_keywords, mock_search):
        """Test when scored search finds nothing."""
        ontology_data = {"relationships": {"relates_to": {}}}
        mock_keywords.return_value = "auth handler"
        mock_search.return_value = []

        result = get_relationship_suggestions(ontology_data, "/src/auth.py", "_semantic/decisions")
        assert result == ""

    @patch("hooks.post_tool_use.find_related_memories_scored")
    @patch("hooks.post_tool_use.extract_keywords_from_path")
    @patch("hooks.post_tool_use.infer_relationship_type")
    def test_multiple_results(self, mock_infer, mock_keywords, mock_search):
        """Test with multiple related memories."""
        ontology_data = {"relationships": {"relates_to": {}, "supersedes": {}}}
        mock_keywords.return_value = "auth handler"
        mock_search.return_value = [
            {
                "id": "aaa-111",
                "title": "Memory 1",
                "path": "/p/1.memory.md",
                "score": 80,
                "namespace": "_semantic/decisions",
                "tags": [],
                "match_reasons": [],
            },
            {
                "id": "bbb-222",
                "title": "Memory 2",
                "path": "/p/2.memory.md",
                "score": 60,
                "namespace": "_semantic/decisions",
                "tags": [],
                "match_reasons": [],
            },
            {
                "id": "ccc-333",
                "title": "Memory 3",
                "path": "/p/3.memory.md",
                "score": 40,
                "namespace": "_procedural/patterns",
                "tags": [],
                "match_reasons": [],
            },
        ]
        mock_infer.side_effect = ["Supersedes", "RelatesTo", "RelatesTo"]

        result = get_relationship_suggestions(ontology_data, "/src/auth.py", "_semantic/decisions")

        assert "Memory 1" in result
        assert "Memory 2" in result
        assert "Memory 3" in result
        assert "[supersedes]" in result
        assert "[relates-to]" in result

    @patch("hooks.post_tool_use.find_related_memories_scored")
    @patch("hooks.post_tool_use.extract_keywords_from_path")
    @patch("hooks.post_tool_use.infer_relationship_type")
    def test_output_format(self, mock_infer, mock_keywords, mock_search):
        """Test output starts with correct header."""
        ontology_data = {"relationships": {"relates_to": {}}}
        mock_keywords.return_value = "config"
        mock_search.return_value = [
            {
                "id": "abc-123",
                "title": "Config Setup",
                "path": "/p/1.memory.md",
                "score": 30,
                "namespace": "_semantic/decisions",
                "tags": [],
                "match_reasons": [],
            },
        ]
        mock_infer.return_value = "RelatesTo"

        result = get_relationship_suggestions(ontology_data, "/src/config.py", "_semantic/decisions")

        assert result.startswith("\nSuggested relationships")
        assert "[relates-to]" in result
        assert "Config Setup" in result


class TestInferRelationshipType:
    """Test infer_relationship_type() function — now returns PascalCase."""

    def test_same_namespace_very_high_overlap_supersedes(self):
        """Same namespace + very high title overlap (>70%) -> Supersedes."""
        target = {
            "title": "Use Redis for caching",
            "namespace": "_semantic/decisions",
            "tags": ["redis", "caching"],
        }
        result = infer_relationship_type(
            source_title="Use Redis for caching layer",
            source_namespace="_semantic/decisions",
            source_tags=["redis"],
            target_metadata=target,
        )
        assert result == "Supersedes"

    def test_same_namespace_high_overlap_conflicts_with(self):
        """Same namespace + high overlap (50-70%) -> ConflictsWith."""
        target = {
            "title": "Redis caching strategy overview",
            "namespace": "_semantic/decisions",
            "tags": ["redis"],
        }
        result = infer_relationship_type(
            source_title="Redis caching implementation plan",
            source_namespace="_semantic/decisions",
            source_tags=["redis"],
            target_metadata=target,
        )
        # "redis" and "caching" overlap out of larger sets -> between 0.5 and 0.7
        assert result in ("ConflictsWith", "Supersedes")

    def test_procedural_to_semantic_implements(self):
        """Procedural source + semantic target + moderate overlap -> Implements."""
        target = {
            "title": "Redis caching decision",
            "namespace": "_semantic/decisions",
            "tags": ["redis"],
        }
        result = infer_relationship_type(
            source_title="Redis caching pattern",
            source_namespace="_procedural/patterns",
            source_tags=["redis"],
            target_metadata=target,
        )
        assert result == "Implements"

    def test_different_namespace_moderate_overlap_derived_from(self):
        """Different namespace + moderate overlap -> DerivedFrom."""
        target = {
            "title": "Redis caching strategy",
            "namespace": "_episodic/sessions",
            "tags": ["redis"],
        }
        result = infer_relationship_type(
            source_title="Redis caching decision",
            source_namespace="_semantic/decisions",
            source_tags=["redis"],
            target_metadata=target,
        )
        assert result == "DerivedFrom"

    def test_low_overlap_relates_to(self):
        """Low overlap -> RelatesTo (default)."""
        target = {
            "title": "PostgreSQL migration guide",
            "namespace": "_procedural/migrations",
            "tags": ["database"],
        }
        result = infer_relationship_type(
            source_title="API authentication with JWT",
            source_namespace="_semantic/decisions",
            source_tags=["auth"],
            target_metadata=target,
        )
        assert result == "RelatesTo"

    def test_same_namespace_low_overlap_relates_to(self):
        """Same namespace but low overlap -> RelatesTo."""
        target = {
            "title": "Logging strategy",
            "namespace": "_semantic/decisions",
            "tags": ["logging"],
        }
        result = infer_relationship_type(
            source_title="API authentication",
            source_namespace="_semantic/decisions",
            source_tags=["auth"],
            target_metadata=target,
        )
        assert result == "RelatesTo"

    def test_empty_title(self):
        """Empty title -> RelatesTo (default)."""
        target = {"title": "", "namespace": "_semantic/decisions", "tags": []}
        result = infer_relationship_type(
            source_title="Some title",
            source_namespace="_semantic/decisions",
            source_tags=[],
            target_metadata=target,
        )
        assert result == "RelatesTo"

    def test_missing_namespace(self):
        """Missing namespace + high overlap -> DerivedFrom (different namespace path)."""
        target = {"title": "Same title words here", "tags": []}
        result = infer_relationship_type(
            source_title="Same title words",
            source_namespace="_semantic/decisions",
            source_tags=[],
            target_metadata=target,
        )
        # No namespace in target means different namespace from source,
        # and high title overlap (>0.3) -> DerivedFrom
        assert result == "DerivedFrom"

    def test_exact_same_title_same_namespace(self):
        """Exact same title + namespace -> Supersedes."""
        target = {
            "title": "Use Redis for caching",
            "namespace": "_semantic/decisions",
            "tags": [],
        }
        result = infer_relationship_type(
            source_title="Use Redis for caching",
            source_namespace="_semantic/decisions",
            source_tags=[],
            target_metadata=target,
        )
        assert result == "Supersedes"

    def test_returns_pascal_case_type(self):
        """Result must be a PascalCase MIF type."""
        target = {"title": "anything", "namespace": "_semantic/knowledge", "tags": []}
        result = infer_relationship_type(
            source_title="something else",
            source_namespace="_procedural/patterns",
            source_tags=[],
            target_metadata=target,
        )
        valid_types = {
            "RelatesTo",
            "Supersedes",
            "ConflictsWith",
            "DerivedFrom",
            "Implements",
            "PartOf",
            "Uses",
            "Created",
            "MentionedIn",
        }
        assert result in valid_types
