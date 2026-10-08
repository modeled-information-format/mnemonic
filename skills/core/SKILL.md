---
name: core
description: >
  This skill should be used when the user says "capture memory", "save to memory",
  "remember this", or trigger phrases like: "I've decided", "let's use", "we're going with",
  "I learned", "turns out", "TIL", "discovered", "I'm stuck", "blocked by",
  "always use", "never do", "convention is". Also triggers on recall phrases:
  "what did we decide", "how do we handle", "remind me", "search memories".
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---


<!-- BEGIN MNEMONIC PROTOCOL -->
## Memory

Search first: `/mnemonic:search {relevant_keywords}`
Capture after: `/mnemonic:capture {namespace} "{title}"`

Run `/mnemonic:list --namespaces` to see available namespaces from loaded ontologies.
<!-- END MNEMONIC PROTOCOL -->

# Mnemonic Core

Memory system operations. See `references/` for full documentation.

## Trigger Phrases

### Capture Triggers (silently capture when user says):

**Decisions** (namespace: _semantic/decisions):
- "I've decided", "let's use", "we're going with"
- "we'll use", "I'm choosing", "going forward with"
- "the decision is", "we chose", "decided on"

**Learnings** (namespace: _semantic/knowledge):
- "I learned", "turns out", "discovered that"
- "TIL", "gotcha", "found out", "realized"
- "the root cause was", "it was because"

**Patterns** (namespace: _procedural/patterns):
- "always use", "never do", "when X do Y"
- "the pattern is", "we should always", "convention is"
- "standard approach", "best practice here"

**Blockers** (namespace: _episodic/sessions/blockers):
- "I'm stuck on", "blocked by", "can't figure out"
- "hitting a wall", "the problem is", "struggling with"

**Context** (namespace: _semantic/knowledge):
- "important to know", "keep in mind", "context is"
- "background", "constraint", "requirement"

### Recall Triggers (search memories when user asks):

- "what did we decide about", "how do we handle"
- "what's our approach to", "check for decisions"
- "any learnings about", "patterns for"
- "remind me", "what do we know about"
- "search memories", "recall", "find memories"

### Silent Capture Protocol

**When to capture:** Only capture when the user explicitly states a decision, learning, pattern, or blocker in their message. Do NOT capture based on Claude's own suggestions or recommendations.

**When trigger phrases are detected:**
1. Capture to appropriate namespace WITHOUT announcing
2. Do NOT say "I'm capturing this" or similar
3. Continue natural conversation flow
4. Memory creation is invisible to user

**Do NOT capture:**
- Claude's own suggestions (only user-stated facts)
- Hypothetical scenarios ("we could use...")
- Questions or exploratory discussion

### Visibility & Review

Users can review captured memories at any time:

```bash
# Check session status and recent captures
/mnemonic:status

# List recent memories (last 7 days)
find ${MNEMONIC_ROOT} -name "*.memory.md" -mtime -7 -exec basename {} \;

# Search for specific captures
/mnemonic:search {keywords}
```

**If a user asks "what did you capture?" or "show me my memories":**
- Run `/mnemonic:status` to show memory stats
- Use search to find recent relevant memories
- This is NOT a violation of silent capture - user explicitly requested visibility

## Capture

```bash
/mnemonic:capture {namespace} "{title}"
```

Namespaces: `_semantic/decisions` | `_semantic/knowledge` | `_procedural/patterns` | `_episodic/blockers` | `_episodic/sessions`

**MANDATORY: Before creating any memory, check for duplicates:**

1. Search for existing memories with similar keywords:
   ```bash
   rg -i "{key_words}" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l | head -5
   ```

2. If matches found, read the top result
3. If it covers the same topic → UPDATE existing memory (use Edit tool) instead of creating new
4. If related but different → create new memory with a `relates-to` relationship
5. Only create brand new if no matches found

## Recall

```bash
rg -i "{keywords}" ${MNEMONIC_ROOT}/ --glob "*.memory.md" -l
```

## Minimal Memory Format

**CRITICAL: Generate real values. NEVER write placeholders like "PLACEHOLDER_UUID" or "PLACEHOLDER_DATE".**

Generate a UUID and timestamp FIRST, then write the file:

```bash
# Generate these BEFORE writing the memory file
UUID=$(uuidgen 2>/dev/null | tr '[:upper:]' '[:lower:]')
[ -z "$UUID" ] && UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**Type must match namespace path:**
- `_semantic/*` → `type: semantic`
- `_procedural/*` → `type: procedural`
- `_episodic/*` → `type: episodic`

Then create the file with the real generated values:

```yaml
---
id: <the real UUID generated above>
title: "Your actual title here"
type: semantic
namespace: _semantic/decisions
created: <the real DATE generated above>
temporal:
  validFrom: <the real DATE generated above>
  recordedAt: <the real DATE generated above>
  lastAccessed: <the real DATE generated above>
  decay:
    model: exponential
    halfLife: P90D
    strength: 1.0
provenance:
  sourceType: agent_inferred   # user_explicit if the user stated it directly
  agent: claude
  confidence: 0.9
---

# Your actual title here

Content here.
```

Half-life defaults:
- `_semantic/decisions`: P180D (long-lived)
- `_semantic/knowledge`: P90D
- `_procedural/patterns`: P180D (long-lived)
- `_episodic/*`: P30D (fast decay)

## References

- `references/capture.md` - Full capture workflow
- `references/recall.md` - Search and retrieval patterns
- `references/schema.md` - Complete MIF Level 3 schema
- `references/examples.md` - Working examples
