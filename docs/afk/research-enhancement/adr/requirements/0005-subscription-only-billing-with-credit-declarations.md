# Billing: subscription only, credit balance declared disabled

> Status: Accepted
> Audited: 2026-09-11
> Layer: Requirements
> Context ticket: research-enhancement

`consultation.billing` defaults to `subscription_only`. A participant runs only when its auth gate reports a subscription login; API keys in the environment or the CLI config, gateway credentials and enterprise cloud modes are refused, never fallen back to (PRD AC-024, AC-025). Quota exhaustion ends the participant for the window (AC-026). Because a subscription CLI may draw an enabled credit balance silently, the administrator declares `credits: disabled` per destination and the dispatcher probes headroom where the CLI reports it; the setup docs tell the user to keep the Codex balance at 0 with auto-reload off (AC-027). Source: `MERGED-PLAN.md` §5, §6 D-5.
