export const QUALITY_LABEL: Record<string, string> = {
  valid: "有效",
  out_of_reference_range: "超出参考区间",
  below_lod: "低于检出限",
  below_lod_imputed: "低于检出限（替代值）",
  missing: "缺失",
  unit_error: "单位错误",
  invalid_value: "数值无效",
  implausible: "超出可接受范围",
};

export const BIOMARKER_ORDER = [
  "albumin",
  "creatinine",
  "glucose",
  "crp",
  "lymphocyte_pct",
  "mcv",
  "rdw",
  "alp",
  "wbc",
];

export function fmt(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return "—";
  return Number(v.toFixed(digits)).toString();
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}
