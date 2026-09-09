---
name: to-demo-plan
description: Deprecated alias for to-meeting-d. Demo script for a delivered feature — synthesizes its specs + diff into minute-budgeted DEMO-PLAN.md. Use when the user wants to demo a feature to POs, QA, or stakeholders, or asks for the stakeholder demo meeting, the company meeting, or a one-hour demo to a four-role audience.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# to-demo-plan — compatibility alias

Print this line once, then continue:

> `/afk:to-demo-plan` is the old name. The skill is now `/afk:to-meeting-d`. The alias is removed in the next major version.

Then read `${AFK_PLUGIN_ROOT}/skills/afk/to-meeting-d/SKILL.md` and follow it verbatim with the same arguments, including any this file was invoked with. Add nothing of your own and skip nothing; this file holds no behaviour of its own.

Everything the forwarded skill needs lives beside it — its template, its shared format file, its index row. This directory holds this file only.
