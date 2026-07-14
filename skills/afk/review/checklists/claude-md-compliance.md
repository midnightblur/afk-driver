# claude-md-compliance — documented-rule violations

Default `class: compliance`. Documented rules are hard findings — PRECEDENCE.md's baseline softening does not apply here.

Load the resolved CLAUDE.md chain; for each documented rule, check the diff for a violation. This concern enforces the target repo's CLAUDE.md chain — landmines documented there (e.g. tenant/security test helpers, formatter discipline) live there, not here. The recurring landmines below are **not** homed in that chain — flag any the diff trips:

- `@Transactional(rollbackFor=…)` must be repeated on **every** override, not just the base — a subclass override that calls `super.x()` bypasses the proxy and silently commits on a checked exception.
- Cost Center and Profit Center must be sourced as a **pair** from one source — never mixed.
- **Never** hand-write `UpgradeGroup_*.java`, `PreDbMigration`, or `db/changelog/*`; add JPA `@Entity` classes and let liquibase-hibernate7 pick them up. An `@Entity` in the diff with no passing pickup is a violation.
- Jackson 3 / SB4: a new enum needs `@Skip` or `@GenerateEnumSwaggerSchema`; `@JsonDeserialize` annotations live under `tools.jackson.databind.annotation`; a `@Builder` DTO without `@NoArgsConstructor` breaks J3 creator visibility.
- `*-ui` npm deps must be ≥30 days old and **exact-pinned** (incl. transitive) — no carets/tildes, no fresh-published versions.
- The access boundary to verify is **company and/or vendor**, not tenant (build-per-tenant = single-tenant at runtime).
- Cross-module edits (outside the home module) carry a `// {TICKET-ID}:` marker comment in the added hunks.
- Commits start with `[{NNNN-slug}]`.
- Any rule stated in a service/sub-package `CLAUDE.md` that the diff contradicts — quote the rule and the offending line.
