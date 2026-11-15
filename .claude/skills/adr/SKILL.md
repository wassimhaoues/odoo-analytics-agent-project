---
name: adr
description: Record an architecture decision as docs/adr/NNNN-title.md. Use when choosing a technology, changing a contract (tracking schema, event version, addon boundary), or making any decision someone will later ask "why is it like this?".
---

# Architecture Decision Record

1. Next number: `ls docs/adr | sort | tail -1` → +1, zero-padded to 4.
2. File `docs/adr/NNNN-kebab-title.md`:

```markdown
# NNNN. Title in sentence case

- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## Context
What forces are at play. Facts, constraints, what we tried.

## Decision
What we chose, stated plainly.

## Consequences
What gets easier, what gets harder, what we must now do.

## Alternatives considered
Each option in one or two lines, with why it lost.
```

3. Add a line to `docs/adr/README.md` (index).
4. Never edit an accepted ADR's decision. Write a new one that supersedes it.
