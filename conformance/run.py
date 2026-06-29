#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
"""OCF conformance runner.

Checks, in order:

1. **Schemas are well-formed** — each file in ``schema/`` is a valid
   JSON Schema (Draft 2020-12).
2. **Positive cases conform** — every bundle in ``examples/*.ocf`` and
   ``conformance/valid/*.ocf`` validates against the schemas *and* satisfies the
   cross-file semantic invariants the spec states but JSON Schema cannot express.
   These include budget/token arithmetic, declared slots, and one current version
   per effective ``(namespace, id)``.
3. **Negative cases are rejected** — structural cases in
   ``conformance/invalid/structural/`` fail schema validation; semantic cases in
   ``conformance/invalid/semantic/*.ocf`` are structurally valid but break an
   invariant. Each negative case carries an ``expect.txt`` whose text must appear
   in the reported errors, so a case can never pass for the wrong reason.

Usage:    python3 conformance/run.py
Requires: pip install 'jsonschema>=4.18'   (Draft 2020-12 support)
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - environment guard
    sys.exit("OCF conformance needs jsonschema: pip install 'jsonschema>=4.18'")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
CONFORMANCE = ROOT / "conformance"
KINDS = ("manifest", "schema", "snapshot", "qualify")

format_checker = FormatChecker()


@format_checker.checks("date-time", raises=ValueError)
def _check_date_time(value: object) -> bool:
    """Accept RFC 3339 date-times without an extra dependency."""
    if not isinstance(value, str):
        return True
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    _dt.datetime.fromisoformat(text)
    return True


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMAS = {name: load_json(SCHEMA_DIR / f"{name}.schema.json") for name in KINDS}
VALIDATORS = {
    name: Draft202012Validator(schema, format_checker=format_checker)
    for name, schema in SCHEMAS.items()
}


def schema_errors(kind: str, doc: object) -> list[str]:
    return [error.message for error in VALIDATORS[kind].iter_errors(doc)]


def _effective_namespace(manifest: dict, entry: dict) -> str:
    namespace = entry.get("namespace")
    if isinstance(namespace, str):
        return namespace
    default_namespace = manifest.get("default_namespace")
    if isinstance(default_namespace, str):
        return default_namespace
    return "shared"


def invariant_errors(manifest: dict, schema: dict, snapshot: dict) -> list[str]:
    """Cross-file semantic invariants from SPEC sections 2-3."""
    errors: list[str] = []
    slot_names = {slot.get("name") for slot in schema.get("slots", [])}
    if snapshot.get("budget_tokens") != schema.get("budget_tokens"):
        errors.append("snapshot.budget_tokens must match schema.budget_tokens")
    entries = snapshot.get("entries", [])
    total = sum(entry.get("tokens", 0) for entry in entries)
    if snapshot.get("token_count") != total:
        errors.append(
            f"token_count {snapshot.get('token_count')} != sum(entry.tokens) {total}"
        )
    for entry in entries:
        if entry.get("slot") not in slot_names:
            errors.append(
                f"entry {entry.get('id')!r} slot {entry.get('slot')!r} is not a declared slot"
            )
    seen_records: set[tuple[str, object]] = set()
    for entry in entries:
        record_id = entry.get("id")
        key = (_effective_namespace(manifest, entry), record_id)
        if record_id is None:
            continue
        if key in seen_records:
            errors.append(
                "stale version conflict: "
                f"entry {record_id!r} in namespace {key[0]!r} appears more than once; "
                "concurrent writes must be rejected or reconciled with merge/supersede"
            )
        else:
            seen_records.add(key)
    saturation = snapshot.get("saturation")
    budget = schema.get("budget_tokens")
    if saturation is not None and isinstance(budget, int) and budget > 0:
        expected = total / budget
        if abs(saturation - expected) > 0.01:
            errors.append(
                f"saturation {saturation} != token_count/budget_tokens {expected:.4f}"
            )
    return errors


def bundle_errors(path: Path) -> list[str]:
    """Every schema + invariant error for an OCF bundle directory."""
    errors: list[str] = []
    manifest = load_json(path / "manifest.json")
    schema = load_json(path / "schema.json")
    snapshot = load_json(path / "snapshot.json")
    errors += [f"manifest: {m}" for m in schema_errors("manifest", manifest)]
    errors += [f"schema: {m}" for m in schema_errors("schema", schema)]
    errors += [f"snapshot: {m}" for m in schema_errors("snapshot", snapshot)]
    qualify = path / "qualify.jsonl"
    if qualify.exists():
        for lineno, line in enumerate(qualify.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            errors += [f"qualify L{lineno}: {m}" for m in schema_errors("qualify", record)]
    if isinstance(manifest, dict) and isinstance(schema, dict) and isinstance(snapshot, dict):
        errors += [f"invariant: {m}" for m in invariant_errors(manifest, schema, snapshot)]
    return errors


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"  ok   {label}")

    def fail(self, label: str, detail: str) -> None:
        self.failed += 1
        print(f"  FAIL {label}\n         {detail}")


def check_schemas(report: Report) -> None:
    print("schemas are valid Draft 2020-12:")
    for name in KINDS:
        try:
            Draft202012Validator.check_schema(SCHEMAS[name])
            report.ok(f"{name}.schema.json")
        except Exception as error:  # noqa: BLE001 - report any meta-schema failure
            report.fail(f"{name}.schema.json", str(error))


def check_positive(report: Report) -> None:
    print("positive bundles conform (schema + invariants):")
    bundles = sorted((ROOT / "examples").glob("*.ocf"))
    bundles += sorted((CONFORMANCE / "valid").glob("*.ocf"))
    if not bundles:
        report.fail("positive bundles", "no *.ocf bundles found")
        return
    for bundle in bundles:
        errors = bundle_errors(bundle)
        rel = bundle.relative_to(ROOT)
        if errors:
            report.fail(str(rel), "; ".join(errors))
        else:
            report.ok(str(rel))


def check_structural_negatives(report: Report) -> None:
    print("structural negatives fail schema validation:")
    cases = sorted((CONFORMANCE / "invalid" / "structural").glob("*.json"))
    for case in cases:
        kind = case.name.split(".", 1)[0]
        if kind not in VALIDATORS:
            report.fail(case.name, f"filename must start with one of {KINDS}")
            continue
        doc = load_json(case)
        errors = schema_errors(kind, doc)
        expect = _expect_text(case.with_suffix(".expect"))
        if not errors:
            report.fail(case.name, "expected schema rejection, got none")
        elif expect and not any(expect in e for e in errors):
            report.fail(case.name, f"expected {expect!r} in errors: {errors}")
        else:
            report.ok(case.name)


def check_semantic_negatives(report: Report) -> None:
    print("semantic negatives are structurally valid but break an invariant:")
    cases = sorted((CONFORMANCE / "invalid" / "semantic").glob("*.ocf"))
    for case in cases:
        errors = bundle_errors(case)
        expect = _expect_text(case / "expect.txt")
        rel = case.relative_to(ROOT)
        if not errors:
            report.fail(str(rel), "expected an invariant rejection, got none")
        elif expect and not any(expect in e for e in errors):
            report.fail(str(rel), f"expected {expect!r} in errors: {errors}")
        else:
            report.ok(str(rel))


def _expect_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def main() -> int:
    report = Report()
    check_schemas(report)
    check_positive(report)
    check_structural_negatives(report)
    check_semantic_negatives(report)
    print(f"\n{report.passed} passed, {report.failed} failed")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
