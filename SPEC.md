<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Open Cognitive Format (OCF) — Specification v0.1

> Every existing format stores facts. None standardizes what an agent holds in force right now — a
> bounded, schema-governed working set with the governance trail that explains why each entry was
> admitted or rejected. OCF is that missing layer: a portable snapshot of committed working context
> plus its qualify log, so any runtime can *resume* rather than re-retrieve.

OCF standardizes **only** the committed-working-state layer. It *references* the memory **unit**
layer (facts/records) maintained by other formats (PAM, AMP, OAMP, files) rather than redefining it.

## Bundle

An OCF bundle is a directory:

```
<name>.ocf/
  manifest.json     # required — what this is + which unit layer it composes with
  schema.json       # required — the typed slot contract (the ACC S_CCS)
  snapshot.json     # required — the committed working state
  qualify.jsonl     # optional — admit/reject governance log
```

JSON Schemas for each file live in [`schema/`](schema/).

## 1. Manifest — `manifest.json`

| field | type | req | notes |
|---|---|:--:|---|
| `ocf_version` | string | ✓ | `0.1`; readers accept the same major version |
| `agent_id` | string |  | producer id |
| `created` | date-time | ✓ | RFC 3339 |
| `unit_source` | string | ✓ | `inline`, or the unit layer referenced: `pam` / `amp` / `oamp` / `artesian` / `files` |
| `unit_refs` | string[] |  | references into the unit store (when not `inline`) |
| `session` | object |  | optional work-session identity for cross-agent handoff — `{ session_id, task_id, user_id, handed_off_from }` (see [Cross-agent session handoff](#cross-agent-session-handoff)) |

## 2. Schema Declaration — `schema.json`

The contract between the compressor that writes the state and the reasoner that reads it (the ACC
`S_CCS`). It lets a runtime validate compatibility **before** import.

| field | type | req | notes |
|---|---|:--:|---|
| `ocf_version` | string | ✓ |  |
| `slots` | object[] | ✓ | each `{ name, description? }` — the typed slots, in render order |
| `budget_tokens` | integer | ✓ | saturation bound |
| `eviction` | string |  | `lowest-score` \| `oldest` \| `manual` |

## 3. Working Snapshot — `snapshot.json`

The bounded, schema-governed committed state. Each entry is one committed unit, filed into a slot.

| field | type | req | notes |
|---|---|:--:|---|
| `budget_tokens` | integer | ✓ | must match the schema |
| `token_count` | integer | ✓ | sum of entry tokens |
| `saturation` | number |  | `token_count / budget_tokens` |
| `entries[]` | object | ✓ | committed entries |

Each entry:

| field | type | req | notes |
|---|---|:--:|---|
| `id` | string | ✓ | stable within the bundle |
| `slot` | string | ✓ | one of the schema slots |
| `content` | string | ✓ | may be empty when `resolution = pointer` |
| `tokens` | integer | ✓ |  |
| `score` | number | ✓ | committed value (drives eviction) |
| `resolution` | string |  | `full` \| `compressed` \| `pointer` (default `full`) |
| `unit_ref` | string |  | reference into the unit layer |
| `committed_at` | date-time | ✓ |  |
| `last_access` | date-time |  | last time this entry was retrieved — drives recency decay |
| `access_count` | integer |  | times retrieved — reinforcement signal that resists decay/eviction |
| `retrieval_strength` | number |  | soft-dampening multiplier applied to `score` **at retrieval** (default `1.0`); decay lowers it and access raises it, **without** mutating the committed `score` (storage ≠ retrieval strength) |
| `state` | string |  | `active` (default) \| `archived` — archived entries are retained and still `unit_ref`-resolvable, but excluded from default retrieval until restored |

## 4. Qualify Log — `qualify.jsonl`

One JSON object per line, appended in order — the governance trail. It records **admitted and
rejected** decisions, so an importer trusts the right thing and can see what was considered.

| field | type | req | notes |
|---|---|:--:|---|
| `ts` | date-time | ✓ |  |
| `unit_ref` | string | ✓ | the unit considered |
| `admitted` | boolean | ✓ | whether the unit is in force after this decision |
| `decision` | string |  | the governance action: `admit` \| `reject` \| `promote` \| `merge` \| `supersede` \| `decay` \| `archive` \| `evict` (defaults to `admit`/`reject` per `admitted` when absent) |
| `slot` | string\|null |  | the slot it was filed into (`null` if rejected/evicted) |
| `score` | number | ✓ |  |
| `reason` | string |  | e.g. `qualified`, `below relevance threshold (0.18 < 0.20)`, `redundant`, `superseded by <id>`, `decayed (retrieval_strength 0.22)`, `archived (LRU, unused 90d)`, `evicted (budget saturated)` |

The qualify log records **admission and removal alike** — every decay-driven archive, supersession, and
eviction is appended with its `decision` and `reason`, so *forgetting is as explainable and portable as
remembering*. A runtime SHOULD never silently drop a committed unit without a qualify entry.

## Aging, decay & eviction

A long-running store accumulates stale, redundant, and unused entries. OCF separates **storage strength**
from **retrieval strength** (a cognitive-memory distinction): an entry is not deleted just because it is
old — its *accessibility* is dampened, and only a deliberate, logged decision removes it.

- **Recency decay.** A runtime SHOULD derive each entry's `retrieval_strength` from `last_access` and
  `access_count` — e.g. an exponential `e^(-λ·Δt)` on time-since-last-access, bounded below, with a boost
  per access — and rank by `score · retrieval_strength` at retrieval. Decay never mutates the committed
  `score`; it only changes what surfaces first. Each retrieval updates `last_access` / `access_count`.
- **Write-time reconciliation.** When a new unit is semantically close to an existing entry, the runtime
  reconciles instead of duplicating: `admit` (new) · `merge` (fold in) · `supersede` (replace a
  contradicted entry, keeping a pointer to the prior) · `noop`. The chosen action is logged in qualify.
- **Eviction.** When the budget saturates or a policy fires (`oldest` · `lowest-score` · lowest
  `retrieval_strength` (LRU) · TTL · low salience), entries are first **soft-archived** (`state =
  archived`, retained and still `unit_ref`-resolvable) before any hard delete — so an evicted entry can
  be restored and the decision is reversible. Hard deletion is a separate, explicit step.
- **Governance.** Every decay-archive, supersession, and eviction is appended to `qualify.jsonl`. Aging is
  a *logged, reviewable, portable* part of the standard — not a silent background mutation of a private store.

## Dreams (offline consolidation)

A **dream** is an offline pass that reorganizes a store into a cleaner one: duplicates merged,
stale/contradicted entries replaced with the latest value, latent patterns surfaced as new entries, and
unused entries decayed or archived. OCF standardizes the dream as a **bundle-to-bundle** operation:

- **Inputs:** one existing OCF bundle (the committed state) plus zero or more session transcripts /
  short-term signal sources (referenced; redacted as needed).
- **Output:** a **new** OCF bundle. The input is **never mutated** — the output is reviewed and then
  *adopted* (attached to future sessions in place of, or alongside, the input) or *discarded*. This
  review-then-adopt gate is mandatory; a dream never silently overwrites the live store.
- **Promotion ranking** SHOULD weight multiple signals — frequency, relevance, query diversity, recency,
  consolidation, conceptual richness — against thresholds before an entry is admitted to the output.
- **Governance:** every promote / merge / drop / supersede / decay decision the dream makes is recorded in
  the output bundle's `qualify.jsonl`. The dream's reasoning travels *with* the result, in the open format
  — not locked inside a vendor pipeline or a free-text diary. Any other runtime can adopt or re-process it.
- A dream MAY also emit a human-readable narrative (a "dream diary") as a separate artifact for review; the
  diary never feeds promotion decisions.

Run dreams on a schedule (e.g. nightly), on demand, or at a compaction boundary.

## Compatibility & resume

- A runtime MAY refuse an import when `schema.json` is incompatible with its own slots or budget.
- Entries in `snapshot.json` are already qualified; on import a runtime SHOULD restore them without
  re-qualifying.
- `qualify.jsonl` is advisory: it explains the snapshot but is not required to reconstruct it.

## Cross-agent session handoff

OCF's reason to exist is *resume rather than re-retrieve* — and the sharpest case is **resuming on a
different runtime**. A user working a task in one agent (say Codex in an IDE) should be able to switch
to another (say Claude Code), state the task, and continue from exactly where the first agent stopped,
with the committed working state intact. The OCF bundle is precisely that portable session:
`snapshot.json` is the committed working state to restore, and `qualify.jsonl` is the decision trail
that explains it.

### Addressing (multi-dimensional)

A single "current task per user" key is not enough: real deployments run **many users, each with many
concurrent agents, each on multiple tasks**. A resumable bundle is therefore addressed by the tuple

```
(user_id, session_id, task_id)   # who · which work session · which task
```

carried in `manifest.session`. `agent_id` is deliberately **not** part of the address — it identifies
the runtime that *produced* the bundle and changes on handoff (recorded in `session.handed_off_from`).
That is what makes the handoff cross-agent: the resuming runtime matches on `(user, session, task)`,
not on which agent wrote it. The tuple keeps concurrent users/agents/tasks from colliding; the unit
layer (`unit_source` + `unit_refs`, e.g. a Qdrant / sqlite-vec store) handles concurrent reads and
writes through its own tenancy.

### Resume protocol

1. **Checkpoint (producer).** The active runtime keeps the bundle for `(user, session, task)` current —
   appending governance decisions to `qualify.jsonl` and updating `snapshot.json` as entries are
   committed or evicted. It SHOULD checkpoint before yielding (on pause, token exhaustion, or a
   compaction boundary), setting `session.handed_off_from = agent_id`.
2. **Address (consumer).** A different runtime resolves the bundle by `(user_id, session_id, task_id)`.
3. **Restore.** It loads `snapshot.json` and restores the entries **without re-qualifying** (they are
   already committed — see *Compatibility & resume*), after checking `schema.json` compatibility. It MAY
   read the tail of `qualify.jsonl` to understand the most recent admit/reject decisions, and MAY
   hydrate `pointer` / `unit_ref` entries from the referenced unit layer.
4. **Continue.** The runtime proceeds from the restored state — no replay of the original transcript, no
   re-retrieval of the whole corpus.

A runtime that cannot satisfy `schema.json` (incompatible slots / budget) MAY refuse the resume rather
than silently degrade.

### Reference implementation

[Artesian](https://github.com/aquifer-labs/artesian) implements this handoff: it writes OCF bundles
keyed by `(user, session, task)` and exposes `artesian handoff <session>` / a `memory.session.resume`
MCP tool that restores the committed snapshot for a new agent. A session-start hook can auto-resume the
bundle so a user only has to name the task. OCF is the portable contract; an implementation remains
free to store the unit layer however it likes.

## Human control over backend-stored memory

OCF deliberately separates the **bulk memory units** (facts / documents / embeddings, which may live
in a vector database referenced by `unit_source` + `unit_refs`, e.g. `"qdrant"` or `"sqlite-vec"`)
from the **control layer** (`schema.json` + `snapshot.json`). The control layer is small and
human-readable, so an operator can audit and edit — by hand — exactly what the agent holds in force
and how it is governed, even when the underlying memory is a database. A runtime SHOULD treat an
operator's edits to `schema.json` / `snapshot.json` as authoritative on the next import.

## Prior art & relationships

- **ACC / CCS** — Bousetouane, *AI Agents Need Memory Control Over More Context*
  ([arXiv:2601.11653](https://arxiv.org/abs/2601.11653)). The algorithm OCF serializes; OCF is its
  portable on-disk form.
- **Working-memory models** — *ClawVM* (harness-managed virtual memory, typed pages) and *AMV-L*
  (value-driven lifecycle tiers) formalize the bounded working set, but ship no portable format.
- **Portable Agent Memory** ([arXiv:2605.11032](https://arxiv.org/abs/2605.11032)) — a five-component
  portable memory with cryptographic provenance; its *working* component is a flat list and it lists
  temporal validity as future work, so it does not cover OCF's bounded snapshot + qualify log.
- **Unit-layer formats** OCF composes with via `unit_source` / `unit_refs`:
  [Portable AI Memory](https://portable-ai-memory.org),
  [AMP](https://github.com/agentmemoryprotocol/agentmemoryprotocol),
  [OAMP](https://github.com/deep-thinking-lab/open-agent-memory-protocol),
  [MemoryGrain / OMS](https://memorygrain.org), and plain files.
- **[W3C AI-Agent-Memory-Interop](https://www.w3.org/community/ai-agent-memory-interop/)** — the
  encryption / identity envelope; an OCF bundle is a payload inside it.
- **Adjacent stack layers** —
  [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
  (*what an organization knows*), [MCP](https://modelcontextprotocol.io) (*what an agent can do*),
  [ARD](https://github.com/ards-project/ard-spec) (*where to find tools*).
