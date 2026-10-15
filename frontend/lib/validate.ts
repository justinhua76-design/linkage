// Lightweight client-side checks for immediate feedback. The backend is the
// single source of truth: every value is re-validated server-side, and an age
// is only ever produced by the backend's deterministic engine.

export type ParseResult = { ok: true; value: number } | { ok: false; message: string };

const NUMBER_RE = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

export function parseStrictNumber(raw: string): ParseResult {
  const s = raw.trim();
  if (s === "") return { ok: false, message: "必填" };
  if (s.includes(",")) return { ok: false, message: "请使用小数点 (.)，不要使用逗号" };
  if (!NUMBER_RE.test(s)) return { ok: false, message: "请输入数字" };
  const v = Number(s);
  if (!Number.isFinite(v)) return { ok: false, message: "数值无效" };
  if (v < 0) return { ok: false, message: "不能为负数" };
  return { ok: true, value: v };
}

export function ageAt(birthDate: string, onDate: string): number | null {
  const b = new Date(`${birthDate}T00:00:00Z`);
  const d = new Date(`${onDate}T00:00:00Z`);
  if (Number.isNaN(b.getTime()) || Number.isNaN(d.getTime()) || d < b) return null;
  const years = (d.getTime() - b.getTime()) / (365.2425 * 24 * 3600 * 1000);
  return Math.round(years * 100) / 100;
}
