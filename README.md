<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# OCF — Open Cognitive Format

**A portable snapshot of what an AI agent holds in force right now — and why.** Not a memory
archive: the bounded, schema-governed *working context* an agent has committed to, plus the qualify
log that explains how it got there — so any runtime (another model, framework, or machine) can
**resume** the work instead of re-retrieving it.

| Layer | Format | Answers | Reference |
|---|---|---|---|
| **OKF** | [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf) | what an organization *knows* | knowledge-catalog |
| **memory units** | [PAM](https://portable-ai-memory.org) · [AMP](https://github.com/agentmemoryprotocol/agentmemoryprotocol) · [OAMP](https://github.com/deep-thinking-lab/open-agent-memory-protocol) · files | what an agent *has accumulated* | various |
| **OCF** (this) | Open Cognitive Format | what an agent *holds in force now* | [Artesian](https://github.com/aquifer-labs/artesian) |
| **MCP** | [Model Context Protocol](https://modelcontextprotocol.io) | what an agent can *do* | many |
| **ARD** | [Agentic Resource Discovery](https://github.com/ards-project/ard-spec) | where to *find* tools | ards-project |

OKF organizes what a *company* knows (static, curated knowledge); it is **not** an agent's runtime
memory. The agent's *accumulated* facts live in unit formats (PAM / AMP / OAMP / files), and OCF is
the thin layer over them that captures what the agent *currently holds in force* — the gap none of
the others fill.

## The gap OCF fills

Every portable agent-memory format standardizes the memory **unit** (facts / records): Portable AI
Memory, AMP, OAMP, content-addressed grains, plain files. **None** standardizes the agent's
**committed working state** — a bounded, typed working set with a saturation budget — or the
**governance trail** that says why each entry was admitted or rejected. The ACC line of work
(arXiv:2601.11653) formalizes this state — *"retrieved text is not equivalent to a controlled
internal state"* — but publishes no portable format. OCF is that missing layer.

## OCF as the hard-state layer

The current agent-protocol landscape is strongest at transport, discovery, tools, resources, and
agent-to-agent messaging. Those protocols deliberately do not own persistent, committed state: what is
currently in force, who wrote it, how it is partitioned, and why it was admitted. OCF occupies that
hard-state layer. It is a portable format for governed state beneath the message layer, not a
replacement for MCP, A2A, ACP, or similar protocols. Those protocols can expose, move, or operate on an
OCF bundle; OCF defines the inspectable state payload they do not standardize.

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

OCF sits *beneath* MCP / A2A-style messaging as the committed-state payload (an MCP tool can expose an
OCF bundle as a resource) and *inside* a W3C-style encrypted memory cell (OCF is the payload, not the
envelope).

## Human control over backend-stored memory

Moving memory into a vector database usually costs you the thing a markdown wiki gave you: the
ability to *read and correct* what the agent believes. (mem0 says it plainly — memory is
"probabilistic, not perfect," and human correction is "not architected into the pipeline.")

OCF restores that control by splitting two things that are usually fused:

- the **bulk memory units** — facts, documents, embeddings — stay in your backend (Qdrant,
  sqlite-vec, files), referenced by `unit_source` + `unit_refs`. They can be large and opaque.
- the **control layer** — `schema.json` (the typed slots, budget, eviction policy) and
  `snapshot.json` (exactly what is in force right now) — are small, human-readable files an operator
  can open, audit, and **edit by hand**, then hand back to the agent.

So an operator keeps OKF / markdown-style oversight of *what the agent currently believes and how it
is governed*, while the heavy retrieval stays in a real database. You get database scale **and**
human-in-the-loop correction — not one or the other.

## Reference implementation

[Artesian](https://github.com/aquifer-labs/artesian) implements OCF natively:

```bash
artesian kit export --format ocf --output ./session.ocf/   # serialize committed state + qualify log
artesian kit import --format ocf --from  ./session.ocf/    # resume in another runtime
```

## Proof of concept

- A complete minimal bundle: [`examples/minimal.ocf/`](examples/minimal.ocf/) — manifest + schema +
  snapshot + qualify, validatable against [`schema/`](schema/).
- A working reference implementation that produces and consumes OCF today:
  [Artesian](https://github.com/aquifer-labs/artesian) round-trips `kit export --format ocf` through
  `kit import`.
- Validate the example against the schemas:

```bash
pip install check-jsonschema
check-jsonschema --schemafile schema/manifest.schema.json examples/minimal.ocf/manifest.json
check-jsonschema --schemafile schema/schema.schema.json   examples/minimal.ocf/schema.json
check-jsonschema --schemafile schema/snapshot.schema.json examples/minimal.ocf/snapshot.json
```

## Conformance suite

[`conformance/`](conformance/) is a language-neutral test suite — run it to prove a reader/writer
handles OCF correctly. It checks both the JSON-Schema structure and the cross-file invariants the
spec states but JSON Schema cannot express (budgets match, `token_count` equals the entry-token sum,
every entry slot is declared, and each effective `(namespace, id)` has one current version), with
positive bundles plus structural and semantic negative cases (run in CI on every push):

```bash
pip install 'jsonschema>=4.18'
python3 conformance/run.py
```

## Status

`v0.2` draft — deliberately minimal. `v0.1` bundles remain valid; omitted multi-writer fields use the
defaults in the spec. Spec text under CC-BY-4.0; schemas and examples under Apache-2.0.
