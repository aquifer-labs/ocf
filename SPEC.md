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

## 4. Qualify Log — `qualify.jsonl`

One JSON object per line, appended in order — the governance trail. It records **admitted and
rejected** decisions, so an importer trusts the right thing and can see what was considered.

| field | type | req | notes |
|---|---|:--:|---|
| `ts` | date-time | ✓ |  |
| `unit_ref` | string | ✓ | the unit considered |
| `admitted` | boolean | ✓ |  |
| `slot` | string\|null |  | the slot it was filed into (`null` if rejected) |
| `score` | number | ✓ |  |
| `reason` | string |  | e.g. `qualified`, `below relevance threshold (0.18 < 0.20)`, `redundant`, `superseded` |

## Compatibility & resume

- A runtime MAY refuse an import when `schema.json` is incompatible with its own slots or budget.
- Entries in `snapshot.json` are already qualified; on import a runtime SHOULD restore them without
  re-qualifying.
- `qualify.jsonl` is advisory: it explains the snapshot but is not required to reconstruct it.

## Prior art & relationships

- **ACC / CCS** (arXiv:2601.11653) — the algorithm OCF serializes; OCF is its portable on-disk form.
- **Portable AI Memory, AMP, OAMP, content-addressed grains** — unit-layer formats OCF composes
  with via `unit_source` / `unit_refs`.
- **W3C AI-Agent-Memory-Interop** — the encryption / identity envelope; an OCF bundle is a payload.
- **MCP / ARD / OKF** — adjacent stack layers (*do* / *discover* / *organizational knowledge*).
