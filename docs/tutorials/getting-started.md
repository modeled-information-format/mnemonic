# Tutorial: First Project Setup

Learn how to set up Mnemonic for your first project.

## Learning Objectives

By the end of this tutorial, you will:

- Install and configure Mnemonic in a project
- Understand the directory structure
- Verify the installation
- Create your first memory

## Prerequisites

- Claude Code CLI installed
- Git initialized in your project
- Basic command-line familiarity

## Time Required

15 minutes

## Step 1: Add Git Remote (if not already configured)

Mnemonic uses git remote to organize memories by organization and project.

````bash
# Check if remote exists
git remote -v

# Add remote if missing
git remote add origin https://github.com/your-org/your-project.git

# Verify
git remote get-url origin
````

**Expected output:**
````
https://github.com/your-org/your-project.git
````

## Step 2: Load the Plugin

````bash
# One-time setup: add plugin to settings
claude settings plugins add /path/to/mnemonic

# Verify plugin is loaded
claude settings plugins list
````

**Expected output:**
````
Plugins:
  - /path/to/mnemonic
````

## Step 3: Initialize Mnemonic

Run the setup command to configure Mnemonic:

````bash
# Inside Claude Code session
/mnemonic:setup
````

This command will:

1. Detect your current git remote to infer organization and project names
2. Write global Mnemonic config to `~/.config/mnemonic/config.json`
3. Create the unified memory store directory at the configured path (by default `~/.claude/mnemonic/{org}/{project}/`)
4. Initialize the default ontology and index structures in that directory

**What happens:**
- Creates or updates `~/.config/mnemonic/config.json` with organization, project, and memory store path
- Creates `~/.claude/mnemonic/{org}/{project}/` if it does not already exist
- Populates that project directory in the memory store with the default layout used by all Mnemonic commands
- Initializes git repository for versioning at memory store root

## Step 4: Verify Directory Structure

````bash
# Check memory store structure for this project
tree -L 3 ~/.claude/mnemonic/your-org/your-project/
````

**Expected structure:**

````
~/.claude/mnemonic/
├── .git/
└── your-org/
    └── your-project/
        ├── _semantic/
        ├── _episodic/
        └── _procedural/
````

## Step 5: Check System Status

````bash
/mnemonic:status
````

**Example output (will vary by project):**

````
✓ Memory root: ~/.claude/mnemonic/
✓ Organization: your-org
✓ Project: your-project
✓ Git initialized
✓ Total memories: 0
````

## Step 6: Create Your First Memory

Capture a decision about your project:

````bash
/mnemonic:capture _semantic/decisions "Use React for frontend" --tags frontend,architecture
````

**What happens:**
1. Generates UUID for memory
2. Creates `.memory.md` file with frontmatter
3. Opens editor for content
4. Commits to git

**Example memory file:**

````yaml
---
id: 550e8400-e29b-41d4-a716-446655440000
type: semantic
namespace: _semantic/decisions
created: 2026-02-16T17:00:00Z
modified: 2026-02-16T17:00:00Z
title: "Use React for frontend"
tags:
  - frontend
  - architecture
provenance:
  sourceType: agent_inferred
  agent: claude-opus-4
  confidence: 0.95
---

# Use React for Frontend

We decided to use React for our frontend framework.

## Rationale

- Component-based architecture
- Large ecosystem
- Team familiarity
````

## Step 7: Verify Memory Was Created

````bash
# List all memories
/mnemonic:list

# Search for the memory
/mnemonic:search "React"

# Check git history
cd ~/.claude/mnemonic
git log --oneline
````

**Expected:** Memory file appears in search results and git shows commit.

## Step 8: Recall the Memory

````bash
/mnemonic:recall --namespace _semantic/decisions
````

**Expected:** Your React decision memory is displayed.

## Verification Checklist

- [ ] Git remote configured
- [ ] Plugin loaded
- [ ] `/mnemonic:status` shows no errors
- [ ] Directory structure exists
- [ ] First memory created successfully
- [ ] Memory appears in search results
- [ ] Git shows memory commit

## Common Issues

### "No git remote found"

**Solution:** Add git remote in step 1.

### "Plugin not found"

**Solution:** Verify plugin path with `claude settings plugins list`.

### "Permission denied"

**Solution:** Check directory permissions:
````bash
ls -la ~/.claude/
chmod 755 ~/.claude/mnemonic
````

See [Troubleshooting Guide](../troubleshooting.md) for more issues.

## Next Steps

Now that you have Mnemonic set up, continue learning:

1. **[CLI Usage](../cli-usage.md)** - Learn all Mnemonic commands
2. **[Ontologies Guide](../ontologies.md)** - Explore memory types and namespaces
3. **[Architecture](../architecture.md)** - Create a comprehensive project knowledge base

## What You Learned

- ✓ How to install and configure Mnemonic
- ✓ Understanding the directory structure
- ✓ Creating and verifying memories
- ✓ Using basic Mnemonic commands

## Further Reading

- [Architecture](../architecture.md) - How Mnemonic works
- [CLI Usage](../cli-usage.md) - Command-line operations
- [MIF Specification](https://mif-spec.dev) - Modeled Information Format standard
