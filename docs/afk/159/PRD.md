# #159 — Page tips for feature terms and IDs

## Problem Statement

Page readers cannot resolve a feature term or page ID from its visible use. They must search or scroll to find its meaning. Shared glossary tips do not cover feature-specific terms or IDs.

## Solution

Each page document can carry feature-term definitions and ID-to-title mappings. Hover shows this page-owned text wherever the matching term or ID appears. Shared glossary tips remain a fallback. Existing page documents keep their current behavior.

## Catalog

| ID | Tip kind | Source | Match | Result |
|---|---|---|---|---|
| TIP-01 | Page feature term | Current page document | Existing term boundaries, case handling, and plural handling | Show the page definition. |
| TIP-02 | Page ID | Current page document | Complete identifier with the same case | Show the title of the named item. |
| TIP-03 | Shared term | Plugin or repository glossary | Existing shared-term rules | Show the shared definition when no page-owned tip wins. |
| TIP-04 | Legacy feature tip | Sidecar of a legacy page/0 document | Existing legacy rules | Keep the current rendered tip. |

## User Stories

- As a page reader, I want each feature term and page ID to explain itself on hover, so that I can understand the page without searching elsewhere.
- As a page author, I want tips to live with the page data, so that the page carries its feature-specific meanings.
- As a maintainer, I want legacy pages to keep their current tips, so that this capability does not require a migration.

## Acceptance Criteria

- [ ] AC-001 When visible text matches TIP-01, every matching occurrence shows the page definition on hover.
- [ ] AC-002 When visible text matches TIP-02, every matching occurrence shows the mapped title on hover.
- [ ] AC-003 When visible text differs from a page ID by case, TIP-02 does not match it.
- [ ] AC-004 When a page-owned tip and TIP-03 use the same key, the page-owned tip wins on that page only.
- [ ] AC-005 When TIP-01 and TIP-02 match the same token, the exact TIP-02 match wins.
- [ ] AC-006 When 2 entries in one page-owned catalog can match the same token, page validation refuses the document and names the conflicting field.
- [ ] AC-007 When a page-owned tip has an empty key, page validation refuses the document and names the empty field.
- [ ] AC-008 When a page-owned tip has an empty value, page validation refuses the document and names the empty field.
- [ ] AC-009 When a page has no page-owned match but TIP-03 matches, hover shows the shared definition.
- [ ] AC-010 When no page-owned or shared tip matches, the text stays plain and the page still renders.
- [ ] AC-011 A page tip displays its value as plain text; markup, scripts, and link actions do not run.
- [ ] AC-012 A person with page access can read the page-owned tips; a person without page access receives no page-owned tip data.
- [ ] AC-013 Hover resolves a tip from rendered page data without a page, repository, or external-system request.
- [ ] AC-014 A valid legacy page/0 document with TIP-04 renders its current tips without migration.
- [ ] AC-015 A document with page-owned tips does not consume TIP-04 from a nearby legacy sidecar.
- [ ] AC-016 TIP-01 keeps the existing safe word boundaries and lowercase or plural matching behavior of shared terms.

## Worked examples

### WE-01 — Frequent: feature term

| Input | Visible text | Result |
|---|---|---|
| Page feature term `settle loop` maps to `Repeat review until no actionable finding remains.` | `The settle loop starts.` | Hover on `settle loop` shows the page definition. |

### WE-02 — Edge: repeated page ID

| Input | Visible text | Result |
|---|---|---|
| Page ID `AC-001` maps to `Old page documents still render.` | `AC-001` appears in a card and a summary. `ac-001` also appears. | Both `AC-001` occurrences show the mapped title. `ac-001` stays plain. |

### WE-03 — Risky: conflicting and unsafe text

| Input | Visible text | Result |
|---|---|---|
| Page ID `card` maps to `<b>unsafe</b>`. A page feature term and shared glossary term also use `card`. | `Open the card.` | The exact page ID wins. Hover shows `<b>unsafe</b>` as text. No markup runs. |

## Access & validation policy

| Capability | Permitted roles | Denied roles | Data scope | Validation rules |
|---|---|---|---|---|
| Read a page tip | Person with page access | Person without page access | Page-owned tips first; shared glossary fallback second | Exact IDs beat term matches. Unmatched text stays plain. Hover makes no external request. |
| Author page-owned tips | Page-document writer | Reader without page write access | Current page document | Each catalog entry has 1 non-empty key and 1 non-empty plain-text value. Same-catalog match collisions name the field and fail validation. |
| Render a legacy page | Renderer of a valid legacy page/0 document | Renderer of a document with page-owned tips, for sidecar access | Legacy document and its sidecar | Current rendering stays unchanged. No migration is required. |

## Implementation Decisions

| Part | Duty | Decision |
|---|---|---|
| Page document | Carry feature-local meanings | Store TIP-01 and TIP-02 with the page. [ADR-0002](adr/requirements/0002-page-documents-own-feature-tips.md) |
| Page validator | Reject ambiguous or malformed tip data | Reject empty entries and same-catalog match collisions. |
| Page renderer | Combine permitted sources | Keep page/0 behavior, and limit legacy sidecars to legacy pages. [ADR-0001](adr/requirements/0001-preserve-legacy-pages.md) |
| Tooltip runtime | Resolve one tip per visible match | Use exact page ID, then page feature term, then shared term precedence. [ADR-0003](adr/requirements/0003-resolve-tip-conflicts-deterministically.md) |
| Tooltip runtime | Display safe text | Render tip values as text and resolve them without a hover-time request. |

## Testing Decisions

- Document validation tests prove the empty-entry and collision refusals name the repair field.
- Rendered-page tests prove feature terms, repeated IDs, case boundaries, shared fallback, and unmatched text.
- Precedence tests prove page-owned tips beat shared tips and exact IDs beat terms.
- Safety tests prove tip values stay plain text and hover makes no external request.
- Regression tests prove a legacy page/0 document keeps its sidecar tips and a page-owned-tip document ignores that sidecar.

## Out of Scope

- A coverage audit that refuses a page when a visible term or ID has no tip. That work remains planned separately.
- `/afkv2:gc` branch cleanup. Issue #158 owns that work.

## Further Notes

### Assumptions this PRD rests on

The grill contains no unverified external premise.
