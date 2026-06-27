# Visualization rules

**Every non-trivial layer ships with the visual that carries its signal** —
a reviewer should grasp the design from shape, not prose. Skip the visual
only where the layer is one-line "inherited/default."

**Toolkit (use Mermaid for diagrams — never ASCII):**

| Diagram type | Mermaid block | Best for |
|--------------|---------------|----------|
| Context / topology | `flowchart` or `C4Context` | L1 system, deployment |
| Service interaction | `flowchart LR` | L2 service map |
| Sequence (cross-service / cross-aggregate flow) | `sequenceDiagram` | L2 contract calls, L6 use-case flows, sagas |
| Entity-relation | `erDiagram` | L3 data, L5 domain |
| State machine | `stateDiagram-v2` | L5 aggregate lifecycle, L6 saga state |
| Class / pattern shape | `classDiagram` | L8 patterns (interfaces + impls + relations) |
| Module dependency DAG | `flowchart TB` | L7 modules |
| Quadrant (trade-off) | `quadrantChart` | ADR alternative comparison |
| Pie / mini-stat | `pie` | NFR allocation, latency budget split |
| Timeline | `timeline` | rollout / migration phases |
| Tables | GitHub-flavored MD | NFRs, retry budgets, failure matrix, schema columns |

**Diagram quality rules:**
- Label every node and edge. Unlabeled arrows = rejected.
- Keep one diagram to one concern. If a diagram has >12 nodes, split it.
- Caption every diagram with one sentence stating what to take away.
- Tables must have units in the header (`Latency p95 (ms)`, not `Latency p95`).
- Numbers, not adjectives. "p95 < 200 ms" not "fast".
