# VERIFICATION.md — evidence before completion

One home for verification that crosses skills and repositories.

## Verification loop

1. Turn machine-checkable gaps into facts before planning.
2. Run safe, read-only checks without a permission turn.
3. Refresh external state before reporting it.
4. Verify version and specification claims against primary sources.
5. Check a public contract against its specification before changing it.
6. Run every affected build and test tier, not only the edited module. Before
   a push, run them on each platform in "Before a push".
7. Exercise the changed behavior through its real entry point.
8. Verify self-authored claims with the same evidence bar as external claims.

Completion requires evidence from the full affected scope. A local pass does
not prove a wider build, runtime path, or consumer.

## Before a push

Local runs find failures. Continuous integration (CI) confirms the result.

1. Before each push, run locally the checks that CI runs for the change.
2. Run them on every CI platform the host can reach, in parallel. For a Linux
   runner on a Windows host, use Windows Subsystem for Linux (WSL) or a Linux
   virtual machine.
3. In the change description, name each CI platform the host cannot reach as
   not verified locally.
4. Treat a failure that only CI shows as a gap in the local recipe. Fix the
   recipe and the failure.
5. Merge only after CI is green.

## Git content

After a merge, rebase, cherry-pick, or conflict resolution, compare the landed
content with the intended change. Commit identity alone does not prove that the
content survived.
