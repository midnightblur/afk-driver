**L1-D1**: The proposed decision for the system shape in solution layer 1. This item is recorded in the P2P-2067 solution Grill.

**L1-Q1**: The question that asks whether the known investigation limits are acceptable for the system-shape decision. This item is recorded in the P2P-2067 solution Grill.

**local plugin module**: Code that runs inside the installed AFK plugin process and uses the current worktree and forge adapters.

**background service**: A continuously running local process that owns glossary work independently from an AFK phase invocation.

**central service**: A separately deployed shared application that owns glossary work for multiple repositories.

**external frontier**: Evidence outside the checked repository, such as live forge records, deployment manifests, or consumers in another repository.

**partial ledger**: An investigation record with one or more boundaries that the available search methods could not close.

**L2-D1**: The proposed owner boundary for the shared glossary rules.

**L2-D2**: The proposed call boundary between AFK skills and glossary behavior.

**L2-D3**: The proposed boundary between generic AFK configuration and team-owned glossary configuration.

**L2-D4**: The proposed boundary between glossary rules and forge-provider behavior.

**L2-Q1**: The decision about how to detect deletion of the newest forge record.

**L2-Q2**: The question that asks whether the known L2 investigation limits are acceptable.

**glossary engine**: The plugin module that applies the shared rules for glossary work.

**team glossary manifest**: The team-owned file that declares glossary routes and owner chains.

**forge record adapter**: The plugin module that publishes and validates glossary records through a forge provider.

**description revision**: Provider metadata that identifies the exact merge request description version read by a writer.

**conflict check**: A write guard that rejects the update when the description changed after it was read.

**L3-D1**: The proposed location for glossary definitions and team configuration.

**L3-D2**: The proposed location for evidence created before a Draft merge request exists.

**L3-D3**: The proposed compatibility rule for published record formats.

**L3-D4**: The proposed decision to avoid a second durable data store.

**L3-Q1**: The decision about retention of local evidence before publication.

**L3-Q2**: The question that asks whether the known L3 investigation limits are acceptable.

**Git common directory**: The repository-local Git area shared by all linked worktrees.

**reader-first deployment**: A rollout that updates record readers before any writer emits the new format.

**compatibility repair**: A design adjustment that preserves an existing caller, record, or workflow while the glossary lifecycle is added.

**current-head evidence**: Forge evidence that the provider binds to the exact source revision currently under review.

**proof limit**: A case that the available durable evidence cannot distinguish, so the design states what it cannot guarantee.

**prerequisite adoption merge request**: A separate repository change that installs trusted glossary controls before any feature uses those controls.

**lifecycle-enabled repository**: A repository whose target branch contains a valid `glossary.manifest` pointer and compatible glossary controls.

**strict-choice control**: A Lavish input that permits only its closed token set and does not accept a note or write-in answer.

**provider conformance test**: A test that proves GitLab and GitHub implement one normalized forge contract with the required semantics.

**record namespace**: A stable prefix that assigns one family of forge comments to one parser and replay reducer.

**L9-D6**: The final decision that separates glossary ownership in `GLOSSARY-MAP.md` from delivery routes in `glossary.manifest`.

**L9-D7**: The final decision that routes every lifecycle-aware glossary consumer through one command facade.

**L9-D8**: The final decision to use a new tracked-text-only ranked semantic provider.

**L9-D9**: The final decision for glossary identity metadata and lockstep parser migration.

**L9-D10**: The final decision that local evidence expiry fails closed when activity is unknown.

**L9-D11**: The final decision for forge verb parity and the glossary record namespace.

**HL-1-R3**: The human signature for the persistence fields added after the earlier HL-1 signature.

**HL-4-R3**: The human signature for the ledger-validity invariant changed after the earlier HL-4 signature.

**HL-6**: The human signature for changes that existing callers, records, and workflows will observe.
