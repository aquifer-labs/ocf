<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# OCF conformance suite

A small, language-neutral test suite that an implementation can run to prove it produces and
rejects OCF bundles correctly. It checks two layers:

- **Structure** — every file validates against the JSON Schemas in [`../schema/`](../schema/)
  (Draft 2020-12).
- **Semantics** — the cross-file invariants the [spec](../SPEC.md) states but JSON Schema cannot
  express: a snapshot's `budget_tokens` matches the schema's, `token_count` equals the sum of entry
  tokens, `saturation` matches `token_count / budget_tokens`, every entry's `slot` is one declared
  in the schema, and each effective `(namespace, id)` has only one current committed version.

## Run

```sh
pip install 'jsonschema>=4.18'
python3 conformance/run.py
```

Exit code `0` means conformant. The runner prints one line per case and a final tally.

## Layout

| path | role |
|---|---|
| `valid/*.ocf` | positive bundles that MUST pass schema **and** invariants (the canonical `examples/*.ocf` are also checked) |
| `invalid/structural/<kind>.<case>.json` | a single file that MUST fail its schema (`<kind>` ∈ manifest, schema, snapshot, qualify) |
| `invalid/semantic/*.ocf` | a structurally valid bundle that MUST fail one invariant |

Every negative case carries an `expect.txt` (or a `.expect` sidecar) whose text must appear in the
reported errors, so a case can never pass for the wrong reason.

## Adding a case

- New positive: drop a bundle in `valid/<name>.ocf` — it must pass everything.
- New structural negative: add `invalid/structural/<kind>.<slug>.json` plus a `.expect` sidecar
  naming the schema message fragment.
- New semantic negative: add a bundle in `invalid/semantic/<slug>.ocf` (structurally valid) plus an
  `expect.txt` naming the invariant fragment.

This suite is the reference check for the [Artesian](https://github.com/aquifer-labs/artesian)
implementation and any other OCF reader/writer.
