# How to cut a plan

## The cut

- A subtask builds alone, apart from what `## Blocked by` names. One `## Scope` holds it, usually 1 or 2 globs. One sitting finishes it, about 1 hour.
- Cut along the module rows of SDD §8: one subtask per public interface of a module. A module too large for one subtask means the SDD is too coarse: send the point to `/afkv2:propose-solution`, and invent no split that goes against §8.
- Aim for 4 to 10 subtasks. Over 10: the PRD is too large or the cut is too fine.
- Number the files in rank order. A producer always comes before its consumer.
- A public interface comes from SDD §8 word for word. A missing interface is a gap of the design: send it to `/afkv2:propose-solution`.
- A staple the PRD accepted gets acceptance bullets on the subtask that owns it, and a `## Seams` row where the SDD names one.
- Every acceptance bullet traces to the PRD, the SDD or an ADR.

## The gates

Pick the tiers the change needs.

| Tier | When |
|------|------|
| `static` | always: the compile or lint command, and a grep of each `## Produces` anchor |
| `unit` | behavior worth a test on its own |
| `integration` | wiring across modules, persistence, a framework that picks the code up; the test of a seam this subtask implements, on the real output of the framework |
| `api` | an endpoint a caller reaches directly: the real answer, success and error, and the access guard |
| `e2e` | a flow a user sees, driven in the real UI |

Decide now whether each gate can run in this repository. A live tier needs a running app; the `> App:` line of PLAN.md names it. A command needs its program on the PATH. A gate the repository cannot run has the check cell `not applicable: <reason>`, and the plan check refuses any other form. A check that needs a file names a path the Scope of the subtask or of a subtask it waits on owns, or a file already on the feature branch.

A bullet on a runtime effect ("X happens within Y seconds") needs a check that causes the real condition and asserts the real outcome. A check that only starts the machine does not cover it.

A subtask that writes a narrower copy of an existing type lists each field it drops, and why. A field required only under some configuration gets its own check on the generated output.
