---
name: create-skill
description: Create new agent skills, or edit/improve existing ones, with proper structure, progressive disclosure, and bundled resources. Use when the user wants to create, write, build, edit, update, refactor, or improve a skill (SKILL.md and its sibling files).
---

# Creating & Editing Skills

Covers both directions: authoring a **new** skill from scratch, and **editing** an
existing one. Same structure, structure rules, and review checklist apply to both —
the only difference is where you start.

## Process — new skill

1. **Gather requirements** - ask user about:
   - What task/domain does the skill cover?
   - What specific use cases should it handle?
   - Does it need executable scripts or just instructions?
   - Any reference materials to include?

2. **Draft the skill** - create:
   - SKILL.md with compressed instructions (see "Compression principles" below)
   - Sibling .md files for opt-in flows / literal templates (progressive disclosure)
   - Utility scripts if deterministic operations needed

3. **Review with user** - present draft and ask:
   - Does this cover your use cases?
   - Anything missing or unclear?
   - Should any section be more/less detailed?

## Process — editing an existing skill

1. **Read the whole skill first** — SKILL.md and every sibling it references. Don't
   edit a skill you haven't read end-to-end; partial edits drift from the skill's
   own vocabulary and structure.
2. **Match the existing voice** — terminology, compression level, heading style.
   An edit that reads differently from the surrounding skill is a tell. Reuse the
   skill's own defined terms; don't coin synonyms for concepts it already names.
3. **Make surgical changes** — touch only what the request needs. Don't reflow
   prose, renumber steps, or "improve" adjacent sections that aren't in scope.
4. **Keep the chain consistent** — if the skill hands off to / is fed by other
   skills (e.g. a grill → to-* synthesizer pair), an edit that adds an output or a
   step usually needs the paired skill updated too, or the new content has nowhere
   to land. Name the paired skills and update them in the same pass.
5. **Re-run the Review Checklist** below against the edited file.

## Skill Structure

```
skill-name/
├── SKILL.md           # Main instructions (required)
├── REFERENCE.md       # Detailed docs (if needed)
├── EXAMPLES.md        # Usage examples (if needed)
└── scripts/           # Utility scripts (if needed)
    └── helper.js
```

## SKILL.md Template

```md
---
name: skill-name
description: Brief description of capability. Use when [specific triggers].
---

# Skill Name

## Quick start

[Minimal working example]

## Workflows

[Step-by-step processes with checklists for complex tasks]

## Advanced features

[Link to separate files: See [REFERENCE.md](REFERENCE.md)]
```

## Registration (this plugin)

A new skill is **not loadable until it's registered**. After creating
`skills/<group>/<name>/SKILL.md`, add `"./skills/<group>/<name>"` to the `skills`
array in `.claude-plugin/plugin.json` (keep the list alphabetical within its
group), then run `/reload-plugins`. Editing an existing skill needs no
registration change — just `/reload-plugins`.

## Description Requirements

The description is **the only thing your agent sees** when deciding which skill to load. It's surfaced in the system prompt alongside all other installed skills. Your agent reads these descriptions and picks the relevant skill based on the user's request.

**Goal**: Give your agent just enough info to know:

1. What capability this skill provides
2. When/why to trigger it (specific keywords, contexts, file types)

**Format**:

- Max 1024 chars
- Write in third person
- First sentence: what it does
- Second sentence: "Use when [specific triggers]"

**Good example**:

```
Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when user mentions PDFs, forms, or document extraction.
```

**Bad example**:

```
Helps with documents.
```

The bad example gives your agent no way to distinguish this from other document skills.

## When to Add Scripts

Add utility scripts when:

- Operation is deterministic (validation, formatting)
- Same code would be generated repeatedly
- Errors need explicit handling

Scripts save tokens and improve reliability vs generated code.

## When to Split Files

Split into separate files when:

- SKILL.md exceeds 100 lines
- Content has distinct domains (finance vs sales schemas)
- Advanced features are rarely needed
- Literal templates (report formats, prompt scaffolds) over ~20 lines — move to sibling .md
- Opt-in flows (e.g. "post to remote", "upload artifact") — move to sibling .md

The main workflow stays in SKILL.md. Rare / opt-in paths live in siblings. SKILL.md loads at every invocation; siblings load only when the workflow points to them.

## Compression principles

SKILL.md loads at every invocation. Trim prose, keep precision.

**Compress:**

- Drop articles (a/the), fillers (just/really/basically), hedges (typically/usually/should probably).
- Fragments OK in narrative prose.
- Use arrows for causality (X -> Y).
- One word when one word enough.
- Replace multi-sentence repeats w/ one sentence + cross-ref.
- Prefer tables/bullets over prose when 3+ parallel items exist.

**Do NOT touch:**

- Exact strings: flag names, field names, severity values, error messages, file paths, env var names. Verbatim from spec — never paraphrase.
- Code blocks (rendered verbatim into agent calls / scripts).
- Directives — keep subject + scope precise. "Never modify user's worktree" ≠ "Never modify worktree" (whose worktree? matters for safety).
- Tables (already compact, columns need spacing for readability).
- Hard rules — clarity > brevity. "Never run app, build, tests. Static review only." stays — don't caveman to "No run. Static only."

**Why partial, not full caveman:**

Skills are read by Claude later to execute work. Future Claude reads SKILL.md cold without this session's context. Over-compressing directives drops the subject/scope a future reader needs to act correctly. Compress narrative, preserve precision.

## Review Checklist

After drafting or editing, verify:

- [ ] Description includes triggers ("Use when...")
- [ ] SKILL.md under 100 lines (split first, compress second)
- [ ] No time-sensitive info
- [ ] Consistent terminology
- [ ] Concrete examples included
- [ ] References one level deep
- [ ] No filler / hedges / narrator voice in prose
- [ ] Every directive specifies subject + scope precisely
- [ ] Literal templates (>20 lines) moved to sibling .md
- [ ] Opt-in flows moved to sibling .md, referenced from main workflow
- [ ] All flag / field / aspect names verbatim from spec (no paraphrasing)
- [ ] Tables used where 3+ parallel items exist
- [ ] New skill registered in `.claude-plugin/plugin.json` (create only)
- [ ] Paired/handoff skills updated if the edit changed an input or output
