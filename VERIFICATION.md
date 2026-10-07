# VERIFICATION.md — evidence before completion

One home for verification that crosses skills and repositories.

## Verification loop

1. Turn machine-checkable gaps into facts before planning.
2. Run safe, read-only checks without a permission turn.
3. Refresh external state before reporting it.
4. Verify version and specification claims against primary sources.
5. Check a public contract against its specification before changing it.
6. Run every affected build and test tier, not only the edited module.
7. Exercise the changed behavior through its real entry point.
8. Verify self-authored claims with the same evidence bar as external claims.

Completion requires evidence from the full affected scope. A local pass does
not prove a wider build, runtime path, or consumer.

## Git content

After a merge, rebase, cherry-pick, or conflict resolution, compare the landed
content with the intended change. Commit identity alone does not prove that the
content survived.
