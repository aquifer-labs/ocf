<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# OCF — Open Cognitive Format

**A portable snapshot of what an AI agent holds in force right now — and why.** Not a memory
archive: the bounded, schema-governed *working context* an agent has committed to, plus the qualify
log that explains how it got there — so any runtime (another model, framework, or machine) can
**resume** the work instead of re-retrieving it.

| Layer | Format | Answers |
|---|---|---|
| **OKF** | Open Knowledge Format | what an organization *knows* |
| **OCF** (this) | Open Cognitive Format | what an agent *holds in force* |
| **MCP** | Model Context Protocol | what an agent can *do* |
| **ARD** | Agentic Resource Discovery | where to *find* tools |

## The gap OCF fills

Every portable agent-memory format standardizes the memory **unit** (facts / records): Portable AI
Memory, AMP, OAMP, content-addressed grains, plain files. **None** standardizes the agent's
**committed working state** — a bounded, typed working set with a saturation budget — or the
**governance trail** that says why each entry was admitted or rejected. The ACC line of work
(arXiv:2601.11653) formalizes this state — *"retrieved text is not equivalent to a controlled
internal state"* — but publishes no portable format. OCF is that missing layer.

## Three layers

1. **Schema Declaration** (`schema.json`) — the typed slot contract + budget + eviction policy, so a
   runtime can check compatibility **before** it imports.
2. **Working Snapshot** (`snapshot.json`) — the bounded, schema-governed committed state: typed
   entries with tokens, score, and timestamp.
3. **Qualify Log** (`qualify.jsonl`) — append-only admit/reject decisions with reasons. The part
   nobody else ships.

A bundle is a small, human-readable directory. See [`SPEC.md`](SPEC.md) and
[`examples/minimal.ocf/`](examples/minimal.ocf/).

## Composes with — it does not replace

> OCF does **not** define memory units. Import them from PAM, AMP, OAMP, or any store and reference
> them via `unit_source` + `unit_refs`. OCF adds only what nobody else ships — the bounded committed
> snapshot and the qualify log — plus the schema contract that makes them checkable.

OCF sits *above* MCP (an MCP tool can read an OCF bundle as a resource) and *inside* a W3C-style
encrypted memory cell (OCF is the payload, not the envelope).

## Reference implementation

[Artesian](https://github.com/aquifer-labs/artesian) implements OCF natively:

```bash
artesian kit export --format ocf --output ./session.ocf/   # serialize committed state + qualify log
artesian kit import --format ocf --from  ./session.ocf/    # resume in another runtime
```

## Status

`v0.1` draft — deliberately minimal. Spec text under CC-BY-4.0; schemas and examples under Apache-2.0.
