import { test } from "node:test";
import assert from "node:assert/strict";
import { ageAt, parseStrictNumber } from "./validate.ts";

test("parses plain decimals", () => {
  assert.deepEqual(parseStrictNumber(" 4.5 "), { ok: true, value: 4.5 });
  assert.deepEqual(parseStrictNumber("0"), { ok: true, value: 0 });
  assert.deepEqual(parseStrictNumber("1e-2"), { ok: true, value: 0.01 });
});

test("rejects ambiguous or invalid input", () => {
  for (const s of ["", "  ", "4,5", "abc", "4.5mg", "NaN", "Infinity", "-1", "--1", "0x10"]) {
    assert.equal(parseStrictNumber(s).ok, false, s);
  }
});

test("age at collection", () => {
  assert.equal(ageAt("1976-04-12", "2026-04-12"), 50);
  assert.equal(ageAt("2000-01-01", "1999-01-01"), null);
  assert.equal(ageAt("bad", "2026-01-01"), null);
});
