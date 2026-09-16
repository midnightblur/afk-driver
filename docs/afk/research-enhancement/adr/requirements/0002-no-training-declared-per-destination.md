# Training policy: administrator declaration per destination

> Status: Accepted
> Audited: 2026-09-11
> Layer: Requirements
> Context ticket: research-enhancement

The plugin does not infer a provider's training treatment from its auth type. The repository administrator declares `no_training` per destination in `.afk/config.yaml`, after disabling model improvement or using Team/Enterprise seats; a route that requires the declaration blocks any destination where it is absent (PRD AC-032). The declaration is the administrator's evidence, not the plugin's. Source: `MERGED-PLAN.md` §2 dispute 4 (:60), §6 D-2 (:120).

Change note (2026-09-15): amended after ADR-AUDIT.md; the edit removes text the plan never decided and leaves the user's decision unchanged.
