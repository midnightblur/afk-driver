# Diagnose never fixes; fix runs diagnose

> Layer: Requirements
> Context ticket: small-lane

`/afk:diagnose` used to diagnose and then fix in the same run, so code changed before anyone approved a fix. Now `/afk:diagnose` stops at a diagnosis: the checked symptom, the spec comparison, a failing test as the reproduction, the root cause, a verdict and a fix proposal. It stays usable alone. `/afk:fix` runs the diagnosis, gets approval, fixes, verifies and ships. With this split, a fix always rests on a proven bug and a decision someone made.
