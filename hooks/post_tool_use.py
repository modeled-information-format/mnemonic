#!/usr/bin/env python3
"""
Mnemonic PostToolUse Hook

Outputs capture opportunities after tool use based on ontology patterns.
Patterns are loaded from MIF ontology discovery configuration.
"""

import json
import sys
from pathlib import Path

# Add project root to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mif_compat import to_kebab
from lib.ontology import load_file_patterns, load_ontology_data
from lib.search import (
    detect_namespace_for_file,
    extract_keywords_from_path,
    find_related_memories_scored,
    infer_relationship_type,
)

# Files that are routine and don't warrant capture prompts
ROUTINE_PATTERNS = [
    "test_",
    "__init__",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "tsconfig",
    ".eslintrc",
    ".prettierrc",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "Makefile",
    ".gitignore",
    "LICENSE",
]


def get_relationship_suggestions(ontology_data: dict, file_path: str, namespace: str) -> str:
    """Get relationship suggestions based on ontology.

    Args:
        ontology_data: Loaded ontology data containing relationship types
        file_path: Path to the file being edited
        namespace: Detected namespace for the file

    Returns:
        Formatted string with relationship suggestions, or empty string if none found
    """
    relationships = ontology_data.get("relationships", {})
    if not relationships:
        return ""

    # Extract keywords from file path
    path_keywords = extract_keywords_from_path(file_path)
    if not path_keywords:
        return ""

    # Find related memories using scored search
    # Use path keywords as title and content keywords
    keywords_list = path_keywords.split()
    related = find_related_memories_scored(
        title=path_keywords, namespace=namespace, content_keywords=keywords_list, max_results=5
    )

    if not related:
        return ""

    # Build suggestions with memory IDs, scores, and inferred relationship types
    mem_lines = []
    for result in related:
        # Build target metadata from scored search result (already has metadata)
        target_metadata = {
            "title": result.get("title", ""),
            "namespace": result.get("namespace"),
            "tags": result.get("tags", []),
        }

        # Suggest the MIF 1.4.2 kebab-case token (e.g. relates-to) so agents write it
        rel_type = to_kebab(
            infer_relationship_type(
                source_title=path_keywords, source_namespace=namespace, source_tags=[], target_metadata=target_metadata
            )
        )

        # Format: [rel_type] Title (id: short-id, score: N)
        short_id = result["id"][:12] if result["id"] else "unknown"
        mem_lines.append(f"  - [{rel_type}] {result['title']} (id: {short_id}..., score: {result['score']})")

    if not mem_lines:
        return ""

    mem_display = "\n".join(mem_lines)
    return f"\nSuggested relationships (add to memory frontmatter):\n{mem_display}"


def main():
    # Read hook input from stdin (Claude Code passes JSON via stdin)
    input_data = {}
    try:
        if not sys.stdin.isatty():
            input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        pass

    # Extract tool info from stdin JSON
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", "")

    context_message = None
    ontology_data = load_ontology_data()
    file_patterns = load_file_patterns()

    # Check for significant Write/Edit operations
    if tool_name in ["Write", "Edit"]:
        file_path = tool_input.get("file_path", "")
        skip = ["/tmp/", ".cache/", "node_modules/", ".memory.md"]
        if file_path and not any(x in file_path for x in skip):
            # Skip routine files
            filename = Path(file_path).name
            if any(pat in filename for pat in ROUTINE_PATTERNS):
                print(json.dumps({"continue": True}))
                return

            exts = [".py", ".ts", ".js", ".go", ".rs", ".java"]
            if any(ext in file_path for ext in exts):
                # Get namespace suggestion from ontology
                ns_hint = detect_namespace_for_file(file_path, file_patterns)
                if not ns_hint:
                    ns_hint = "_semantic/decisions or _procedural/patterns"

                # Get relationship suggestions using file path and namespace
                rel_suggestion = get_relationship_suggestions(ontology_data, file_path, ns_hint)

                context_message = f"[POST-EDIT] {file_path} | Namespace: {ns_hint}"
                if rel_suggestion:
                    context_message += rel_suggestion

    # Check for significant Bash operations
    if tool_name == "Bash":
        command = tool_input.get("command", "")

        if "git commit" in command:
            context_message = "[POST-COMMIT] Consider: /mnemonic:capture _semantic/decisions"
        elif "error" in tool_output.lower() or "failed" in tool_output.lower():
            context_message = (
                "[POST-ERROR] Resolved → /mnemonic:capture _semantic/knowledge | Blocking → _episodic/blockers"
            )
        elif any(x in command for x in ["install", "build", "deploy", "migrate"]):
            if "error" not in tool_output.lower():
                if "deploy" in command:
                    ns_hint = "_procedural/runbooks"
                elif "migrate" in command:
                    ns_hint = "_procedural/migrations"
                else:
                    ns_hint = "_procedural/patterns"
                context_message = f"[POST-OP] {command[:60]} | Namespace: {ns_hint}"

    if context_message:
        output = {
            "continue": True,
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context_message},
        }
        print(json.dumps(output))
    else:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
