# Review — 0003-tracker-attach-82c3db8-r3

- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests), refactor-safety, api-contract
- verdict: findings — 1 low; fixed in d08987d
- mutation probe not run (tests run in CI on the human's call)
- head: 20b3e5ea11484cf569adf561466c829a12b0a44c
- counts: crit=0 high=0 med=0 low=1

## r-001 · low · design · `adapters/tracker/jira/api.py:796`
attached entries carry filename/mimeType null when read_back is false or the id is absent from the read-back, undocumented; an id absent from a successful read-back is mislabelled `stored differently`.

- Why: A consumer reading attached[i].filename gets null with no stated contract, and the `stored differently` reason is wrong when nothing was listed under that id.
- Fix: Document the null case in ADAPTERS.md, CONTRACT.md and the tool docstring; give an id missing from a successful read-back its own reason such as `not in the read-back`.
- Concern: api-contract (Null in the contract (Effective Java item 54))
