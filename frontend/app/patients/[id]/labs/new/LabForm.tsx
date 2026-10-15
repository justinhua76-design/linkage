"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BIOMARKER_ORDER } from "@/lib/format";
import type { ApiError, Catalog, Issue, LabResult, Patient, PhenoAgeResult } from "@/lib/types";
import { ageAt, parseStrictNumber } from "@/lib/validate";

interface Row {
  value: string;
  unit: string;
  belowLod: boolean;
  lod: string;
}

const today = () => new Date().toISOString().slice(0, 10);

export default function LabForm({ patient, catalog }: { patient: Patient; catalog: Catalog }) {
  const router = useRouter();
  const markers = useMemo(
    () => BIOMARKER_ORDER.map((c) => catalog.biomarkers.find((b) => b.code === c)!).filter(Boolean),
    [catalog],
  );
  const [collectedOn, setCollectedOn] = useState(today());
  const [age, setAge] = useState(
    patient.birth_date ? String(ageAt(patient.birth_date, today()) ?? "") : "",
  );
  const [rows, setRows] = useState<Record<string, Row>>(() =>
    Object.fromEntries(
      markers.map((m) => [m.code, { value: "", unit: m.allowed_units[0], belowLod: false, lod: "" }]),
    ),
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverIssues, setServerIssues] = useState<Issue[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update(code: string, patch: Partial<Row>) {
    setRows((r) => ({ ...r, [code]: { ...r[code], ...patch } }));
  }

  function onDateChange(v: string) {
    setCollectedOn(v);
    if (patient.birth_date && v) {
      const a = ageAt(patient.birth_date, v);
      if (a !== null) setAge(String(a));
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setServerIssues([]);
    setMessage(null);
    const errs: Record<string, string> = {};
    const measurements = [];
    for (const m of markers) {
      const r = rows[m.code];
      if (r.belowLod) {
        const lod = parseStrictNumber(r.lod);
        if (!lod.ok || lod.value <= 0) {
          errs[m.code] = "低于检出限时须填写大于 0 的检出限";
          continue;
        }
        measurements.push({ biomarker: m.code, value: null, unit: r.unit, below_lod: true, lod: lod.value });
      } else {
        const v = parseStrictNumber(r.value);
        if (!v.ok) {
          errs[m.code] = v.message;
          continue;
        }
        measurements.push({ biomarker: m.code, value: v.value, unit: r.unit });
      }
    }
    const a = parseStrictNumber(age);
    if (!a.ok) errs.age = a.message;
    if (!collectedOn) errs.collected_on = "必填";
    setFieldErrors(errs);
    if (Object.keys(errs).length) {
      setMessage("请修正标红字段。未生成任何年龄结果。");
      return;
    }

    setBusy(true);
    try {
      const labRes = await fetch(`/api/backend/patients/${patient.id}/labs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collected_on: collectedOn, source: patient.is_synthetic ? "synthetic" : "manual_entry", measurements }),
      });
      const labBody = await labRes.json();
      if (!labRes.ok) {
        const err = labBody as ApiError;
        setServerIssues(err.errors ?? []);
        setMessage(err.message);
        return;
      }
      const labs = labBody as LabResult[];
      const calc = await fetch("/api/backend/bioage/phenoage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chronological_age: a.ok ? a.value : null,
          patient_id: patient.id,
          lab_result_ids: labs.map((l) => l.id),
        }),
      });
      const calcBody = await calc.json();
      if (!calc.ok) {
        const err = calcBody as ApiError;
        setServerIssues(err.errors ?? []);
        setMessage(`${err.message}（检测数据已保存，可在指标概览中查看）`);
        return;
      }
      router.push(`/patients/${patient.id}/results/${(calcBody as PhenoAgeResult).result_id}`);
    } catch {
      setMessage("网络错误，请重试");
    } finally {
      setBusy(false);
    }
  }

  const issuesFor = (code: string) => serverIssues.filter((i) => i.field === code);

  return (
    <form className="card" onSubmit={submit} noValidate>
      {message && (
        <div className="alert error" role="alert">
          <div>{message}</div>
          {serverIssues.filter((i) => !markers.some((m) => m.code === i.field)).map((i) => (
            <div key={i.code + i.field}>{i.message}</div>
          ))}
        </div>
      )}
      <div className="row">
        <div className="field">
          <label htmlFor="collected_on">检测日期</label>
          <input id="collected_on" type="date" value={collectedOn} max={today()}
                 onChange={(e) => onDateChange(e.target.value)} aria-invalid={!!fieldErrors.collected_on} />
          {fieldErrors.collected_on && <div className="err">{fieldErrors.collected_on}</div>}
        </div>
        <div className="field">
          <label htmlFor="age">采样时实际年龄（岁）</label>
          <input id="age" inputMode="decimal" value={age} onChange={(e) => setAge(e.target.value)}
                 aria-invalid={!!fieldErrors.age} />
          {fieldErrors.age && <div className="err">{fieldErrors.age}</div>}
          <div className="muted">
            允许 {catalog.age_hard_range[0]}–{catalog.age_hard_range[1]} 岁；模型训练范围 {catalog.age_training_range[0]}–{catalog.age_training_range[1]} 岁
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>指标</th><th>数值</th><th>单位</th><th>低于检出限</th><th>参考区间（通用）</th></tr>
          </thead>
          <tbody>
            {markers.map((m) => {
              const r = rows[m.code];
              const err = fieldErrors[m.code];
              const sv = issuesFor(m.code);
              return (
                <tr key={m.code}>
                  <td>
                    <label htmlFor={`v-${m.code}`}>{m.name_zh}</label>
                    <div className="muted">{m.name_en}</div>
                  </td>
                  <td>
                    <input id={`v-${m.code}`} name={m.code} inputMode="decimal" size={8} value={r.value}
                           disabled={r.belowLod} aria-invalid={!!err || sv.some((i) => i.severity === "error")}
                           onChange={(e) => update(m.code, { value: e.target.value })} />
                    {err && <div className="err">{err}</div>}
                    {sv.map((i) => <div key={i.code} className="err">{i.message}</div>)}
                  </td>
                  <td>
                    <select aria-label={`${m.name_zh} 单位`} id={`u-${m.code}`} value={r.unit}
                            onChange={(e) => update(m.code, { unit: e.target.value })}>
                      {m.allowed_units.map((u) => <option key={u} value={u}>{u}</option>)}
                    </select>
                  </td>
                  <td>
                    {m.supports_lod ? (
                      <>
                        <input type="checkbox" id={`lod-${m.code}`} aria-label="低于检出限" checked={r.belowLod}
                               onChange={(e) => update(m.code, { belowLod: e.target.checked })} />
                        {r.belowLod && (
                          <input aria-label="检出限" placeholder="检出限" size={6} inputMode="decimal" value={r.lod}
                                 onChange={(e) => update(m.code, { lod: e.target.value })} />
                        )}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="muted">
                    {m.reference_low}–{m.reference_high} {m.canonical_unit}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted">
        单位必须与化验单一致；系统会严格换算到模型单位（CRP 以 mg/dL 取自然对数）。CRP 为 0 时请勾选“低于检出限”并填写检出限。
      </p>
      <button type="submit" disabled={busy}>{busy ? "计算中…" : "保存并计算 PhenoAge"}</button>
    </form>
  );
}
