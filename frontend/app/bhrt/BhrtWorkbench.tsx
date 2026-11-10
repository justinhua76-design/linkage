"use client";

import { useState } from "react";
import type { BhrtCatalog, Evaluation, ParseResult, PatientIdentity } from "@/lib/bhrt";
import Prescription from "./Prescription";

type Sex = "female" | "male";
interface LabRow { value: string; unit: string; date: string }

const FEMALE_HISTORY: [string, string][] = [
  ["breast_cancer", "乳腺癌病史"], ["endometrial_cancer", "子宫内膜癌病史"], ["ovarian_cancer", "卵巢癌病史"],
  ["vte", "血栓(VTE/PE)病史"], ["vte_active", "活动性血栓"], ["thrombophilia", "易栓症"],
  ["vte_cleared_by_specialist", "血栓风险已获专科许可"], ["stroke_mi", "卒中/心梗"],
  ["liver_disease_active", "活动性肝病"], ["autoimmune_liver_antibody_positive", "自身免疫肝抗体阳性"],
  ["liver_cleared_by_specialist", "肝病已获专科许可"], ["migraine_with_aura", "先兆偏头痛"],
  ["gallbladder_disease", "胆囊疾病"], ["fibroids", "子宫肌瘤"], ["endometriosis", "子宫内膜异位症"],
];
const MALE_HISTORY: [string, string][] = [
  ["prostate_cancer", "前列腺癌病史"], ["abnormal_dre", "直肠指检异常"], ["desires_fertility", "有生育计划"],
  ["vte", "血栓病史"], ["vte_active", "活动性血栓"], ["thrombophilia", "易栓症"],
  ["vte_cleared_by_specialist", "血栓风险已获专科许可"], ["stroke_mi", "卒中/心梗"],
  ["liver_disease_active", "活动性肝病"], ["liver_cleared_by_specialist", "肝病已获专科许可"],
];
const FAMILY: [string, string][] = [
  ["breast_cancer_first_degree", "一级亲属乳腺癌"], ["breast_cancer_early_onset", "早发乳腺癌家族史"],
  ["brca_carrier", "BRCA 携带者"], ["thrombophilia", "家族易栓症"],
];
const MEDS: [string, string][] = [
  ["anticoagulant", "抗凝药"], ["tamoxifen_or_ai", "他莫昔芬/芳香化酶抑制剂"], ["thyroid_hormone", "甲状腺激素"],
  ["ssri_snri", "SSRI/SNRI"], ["stable_on_transdermal", "已有乳膏稳定疗效记录"],
];

const CRITICAL = new Set([
  "e2", "fsh", "total_t", "prl", "tsh", "alt", "ast", "creatinine", "tc", "tg", "ldl", "hb", "hct", "psa", "lh",
]);

const num = (s: string) => (s.trim() === "" ? null : Number(s));

function Checks({ items, state, set }: {
  items: [string, string][]; state: Record<string, boolean>; set: (k: string, v: boolean) => void;
}) {
  return (
    <div className="checks">
      {items.map(([k, label]) => (
        <label key={k} className="check">
          <input type="checkbox" checked={!!state[k]} onChange={(e) => set(k, e.target.checked)} /> {label}
        </label>
      ))}
    </div>
  );
}

export default function BhrtWorkbench({ catalog }: { catalog: BhrtCatalog }) {
  const [sex, setSex] = useState<Sex>("female");
  const [identity, setIdentity] = useState<PatientIdentity>({ name: "", patientId: "", address: "", tel: "", doctor: "" });
  const [imagingDone, setImagingDone] = useState<Record<string, boolean>>({});
  const [basic, setBasic] = useState({ client_ref: "", age: "", height_cm: "", weight_kg: "", sys: "", dia: "" });
  const [smoker, setSmoker] = useState(false);
  const [stage, setStage] = useState({ repro_stage: "unknown", years_since_fmp: "", uterus: "unknown", bleeding: "none" });
  const [mrs, setMrs] = useState<number[]>(Array(11).fill(0));
  const [adam, setAdam] = useState<boolean[]>(Array(10).fill(false));
  const [complaints, setComplaints] = useState("");
  const [hsdd, setHsdd] = useState(false);
  const [history, setHistory] = useState<Record<string, boolean>>({});
  const [sleepApnea, setSleepApnea] = useState("unknown");
  const [family, setFamily] = useState<Record<string, boolean>>({});
  const [meds, setMeds] = useState<Record<string, boolean>>({});
  const [currentHrt, setCurrentHrt] = useState("");
  const [labDate, setLabDate] = useState("");
  const [labs, setLabs] = useState<Record<string, LabRow>>(() =>
    Object.fromEntries(catalog.analytes.map((a) => [a.code, { value: "", unit: a.canonical_unit, date: "" }])),
  );
  const [tRepeat, setTRepeat] = useState({ value: "", unit: "nmol/L" });
  const [breast, setBreast] = useState({ date: "", modality: "ultrasound", birads: "" });
  const [tvus, setTvus] = useState({ date: "", thickness: "", fibroids: false });
  const [dexa, setDexa] = useState("");
  const [prefs, setPrefs] = useState({
    route: "no_preference", progesterone: "auto", biest: "2:8", supplement: false, poor: false, consent: false,
  });
  const [startDate, setStartDate] = useState("");

  const [reportText, setReportText] = useState("");
  const [parseMsg, setParseMsg] = useState<string[]>([]);
  const [parsed, setParsed] = useState<ParseResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Evaluation | null>(null);

  function applyParse(r: ParseResult) {
    setParsed(r);
    setLabs((prev) => {
      const next = { ...prev };
      for (const l of r.labs) {
        const a = catalog.analytes.find((x) => x.code === l.code);
        const unit = l.unit && a?.units.includes(l.unit) ? l.unit : a?.canonical_unit ?? "";
        if (!next[l.code]) continue;
        next[l.code] = { ...next[l.code], value: String(l.value), unit };
      }
      return next;
    });
    if (r.imaging.birads !== null) setBreast((b) => ({ ...b, birads: String(r.imaging.birads) }));
    if (r.imaging.endometrial_thickness_mm !== null)
      setTvus((t) => ({ ...t, thickness: String(r.imaging.endometrial_thickness_mm) }));
    if (r.imaging.fibroids) setTvus((t) => ({ ...t, fibroids: true }));
    if (r.imaging.done.length)
      setImagingDone((d) => ({ ...d, ...Object.fromEntries(r.imaging.done.map((c) => [c, true])) }));
    setParseMsg([`识别 ${r.labs.length} 项检验，请逐项核对下方数值与单位`, ...r.warnings]);
  }

  async function parse(payload: { text?: string; pdf_base64?: string }) {
    setBusy(true);
    setParseMsg([]);
    try {
      const res = await fetch("/api/backend/bhrt/reports/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) setParseMsg([body.message ?? "解析失败"]);
      else applyParse(body as ParseResult);
    } catch {
      setParseMsg(["网络错误，请重试"]);
    } finally {
      setBusy(false);
    }
  }

  async function onPdf(file: File | undefined) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) return setParseMsg(["PDF 超过 10 MB"]);
    const buf = new Uint8Array(await file.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    await parse({ pdf_base64: btoa(bin) });
  }

  function buildIntake() {
    const labList = Object.entries(labs)
      .filter(([, r]) => r.value.trim() !== "" && !Number.isNaN(Number(r.value)))
      .map(([code, r]) => ({ code, value: Number(r.value), unit: r.unit, collected_on: r.date || labDate || null }));
    const hist: Record<string, unknown> = { ...history };
    if (sex === "male") hist.sleep_apnea = sleepApnea;
    return {
      client_ref: basic.client_ref.trim(),
      sex,
      age: Number(basic.age),
      height_cm: num(basic.height_cm),
      weight_kg: num(basic.weight_kg),
      bp_systolic: num(basic.sys),
      bp_diastolic: num(basic.dia),
      smoker,
      ...(sex === "female"
        ? {
            repro_stage: stage.repro_stage,
            years_since_fmp: num(stage.years_since_fmp),
            uterus_intact: stage.uterus === "unknown" ? null : stage.uterus === "yes",
            abnormal_bleeding: stage.bleeding,
            mrs,
            hsdd_confirmed: hsdd,
            breast_imaging: breast.birads === "" ? null
              : { performed_on: breast.date || null, modality: breast.modality, birads: Number(breast.birads) },
            pelvic_us: tvus.thickness === "" && !tvus.fibroids ? null
              : { performed_on: tvus.date || null, endometrial_thickness_mm: num(tvus.thickness), fibroids: tvus.fibroids },
            dexa_t_score: num(dexa),
          }
        : {
            adam,
            male_total_t_repeat: tRepeat.value === "" ? null
              : { code: "total_t", value: Number(tRepeat.value), unit: tRepeat.unit },
          }),
      top_complaints: complaints.split(/[,，、]/).map((s) => s.trim()).filter(Boolean).slice(0, 3),
      history: hist,
      family: sex === "female" ? family : { thrombophilia: !!family.thrombophilia },
      medications: { ...meds, current_hrt: currentHrt || null },
      labs: labList,
      imaging_done: Object.entries(imagingDone).filter(([, v]) => v).map(([k]) => k),
      preferences: {
        route: prefs.route,
        progesterone: prefs.progesterone,
        biest_ratio: prefs.biest,
        progesterone_cream_supplement: prefs.supplement,
        poor_daily_adherence: prefs.poor,
        pellet_consent_signed: prefs.consent,
      },
      start_date: startDate || null,
    };
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!basic.client_ref.trim() || !basic.age) return setError("请填写客户编号和年龄");
    setBusy(true);
    try {
      const res = await fetch("/api/backend/bhrt/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildIntake()),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.errors?.length ? body.errors.map((x: { field: string; message: string }) => `${x.field}: ${x.message}`).join("；") : body.message);
        return;
      }
      setResult(body as Evaluation);
      setTimeout(() => document.getElementById("result")?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch {
      setError("网络错误，请重试");
    } finally {
      setBusy(false);
    }
  }

  const panelLabs = catalog.panel.filter((p) => !p.imaging_code && (sex === "female" ? p.female : p.male));
  const panelCats = Array.from(new Set(panelLabs.map((p) => p.category)));
  const panelImaging = catalog.panel.filter((p) => p.imaging_code && (sex === "female" ? p.female : p.male));
  const analyte = (code: string) => catalog.analytes.find((a) => a.code === code)!;

  return (
    <>
      <form onSubmit={submit} noValidate className="no-print">
        {/* ---------------------------------------------------------- 1 */}
        <section className="card">
          <h2>1. 报告导入</h2>
          <p className="muted">粘贴化验单 / 影像报告文字，或上传带文字层的 PDF（扫描件需先 OCR）。识别结果会填入下方表格，请逐项核对。</p>
          <textarea rows={6} value={reportText} onChange={(e) => setReportText(e.target.value)}
            placeholder={"例：雌二醇(E2) 18.5 pg/mL\n促卵泡生成素 FSH 68.2 mIU/mL\n乳腺超声 BI-RADS 2类"} />
          <div className="row" style={{ marginTop: 8 }}>
            <button type="button" disabled={busy || !reportText.trim()} onClick={() => parse({ text: reportText })}>识别文字</button>
            <label className="btn-link file">上传 PDF
              <input type="file" accept="application/pdf" hidden onChange={(e) => onPdf(e.target.files?.[0])} />
            </label>
          </div>
          {parseMsg.length > 0 && <div className="alert warn" style={{ marginTop: 8 }}>{parseMsg.map((m) => <div key={m}>{m}</div>)}</div>}
          {parsed && parsed.labs.length > 0 && (
            <details><summary className="muted">查看识别来源（{parsed.labs.length} 行）</summary>
              <ul className="muted">{parsed.labs.map((l) => <li key={l.code}>{l.name_zh}: {l.value} {l.unit ?? "?"} ← <code>{l.source_line}</code></li>)}</ul>
            </details>
          )}
        </section>

        {/* ---------------------------------------------------------- 2 */}
        <section className="card">
          <h2>2. 基本信息</h2>
          <p className="muted">姓名、病历号、住址、电话、医师仅打印在处方单上，不发送到服务器。</p>
          <div className="row">
            {([["name", "患者姓名"], ["patientId", "病历号"], ["tel", "电话"], ["address", "住址"], ["doctor", "医师"]] as [keyof PatientIdentity, string][]).map(([k, label]) => (
              <div className="field" key={k}><label>{label}</label>
                <input value={identity[k]} onChange={(e) => setIdentity({ ...identity, [k]: e.target.value })} /></div>
            ))}
          </div>
          <div className="row">
            <div className="field"><label>客户编号</label><input value={basic.client_ref} onChange={(e) => setBasic({ ...basic, client_ref: e.target.value })} /></div>
            <div className="field"><label>性别</label>
              <select value={sex} onChange={(e) => setSex(e.target.value as Sex)}><option value="female">女</option><option value="male">男</option></select></div>
            <div className="field"><label>年龄</label><input inputMode="numeric" size={4} value={basic.age} onChange={(e) => setBasic({ ...basic, age: e.target.value })} /></div>
            <div className="field"><label>身高 cm</label><input inputMode="decimal" size={5} value={basic.height_cm} onChange={(e) => setBasic({ ...basic, height_cm: e.target.value })} /></div>
            <div className="field"><label>体重 kg</label><input inputMode="decimal" size={5} value={basic.weight_kg} onChange={(e) => setBasic({ ...basic, weight_kg: e.target.value })} /></div>
            <div className="field"><label>血压 mmHg</label>
              <span className="row nowrap"><input inputMode="numeric" size={4} value={basic.sys} onChange={(e) => setBasic({ ...basic, sys: e.target.value })} />/
                <input inputMode="numeric" size={4} value={basic.dia} onChange={(e) => setBasic({ ...basic, dia: e.target.value })} /></span></div>
            <label className="check"><input type="checkbox" checked={smoker} onChange={(e) => setSmoker(e.target.checked)} /> 吸烟</label>
          </div>
          {sex === "female" && (
            <div className="row">
              <div className="field"><label>生殖分期</label>
                <select value={stage.repro_stage} onChange={(e) => setStage({ ...stage, repro_stage: e.target.value })}>
                  <option value="unknown">— 请选择 —</option><option value="cycling">规律月经</option>
                  <option value="perimenopause">围绝经期（月经不规律）</option><option value="postmenopause">绝经（≥12 个月无月经）</option>
                  <option value="surgical_or_poi">手术绝经 / POI</option></select></div>
              <div className="field"><label>末次月经距今（年）</label><input inputMode="decimal" size={4} value={stage.years_since_fmp} onChange={(e) => setStage({ ...stage, years_since_fmp: e.target.value })} /></div>
              <div className="field"><label>子宫</label>
                <select value={stage.uterus} onChange={(e) => setStage({ ...stage, uterus: e.target.value })}>
                  <option value="unknown">— 请选择 —</option><option value="yes">保留</option><option value="no">已切除</option></select></div>
              <div className="field"><label>异常子宫出血</label>
                <select value={stage.bleeding} onChange={(e) => setStage({ ...stage, bleeding: e.target.value })}>
                  <option value="none">无</option><option value="evaluated_benign">有，已评估为良性</option><option value="undiagnosed">有，未明确诊断</option></select></div>
            </div>
          )}
        </section>

        {/* ---------------------------------------------------------- 3 */}
        <section className="card">
          <h2>3. 症状评分</h2>
          {sex === "female" ? (
            <div className="grid2">
              {catalog.mrs_items.map((label, k) => (
                <div key={label} className="row nowrap between">
                  <span>{k + 1}. {label}</span>
                  <select value={mrs[k]} onChange={(e) => setMrs(mrs.map((v, j) => (j === k ? Number(e.target.value) : v)))}>
                    {["0 无", "1 轻", "2 中", "3 重", "4 极重"].map((t, v) => <option key={v} value={v}>{t}</option>)}
                  </select>
                </div>
              ))}
            </div>
          ) : (
            <div className="checks">
              {catalog.adam_items.map((label, k) => (
                <label key={label} className="check"><input type="checkbox" checked={adam[k]}
                  onChange={(e) => setAdam(adam.map((v, j) => (j === k ? e.target.checked : v)))} /> {k + 1}. {label}</label>
              ))}
            </div>
          )}
          <div className="field" style={{ marginTop: 12 }}><label>主要诉求（最多 3 项，逗号分隔）</label>
            <input style={{ width: "100%" }} value={complaints} onChange={(e) => setComplaints(e.target.value)} placeholder="如：睡眠差，潮热，性欲低" /></div>
          {sex === "female" && (
            <label className="check"><input type="checkbox" checked={hsdd} onChange={(e) => setHsdd(e.target.checked)} />
              医师已确认性欲减退障碍（HSDD）：已排除伴侣关系、SSRI、GSM 疼痛等因素</label>
          )}
        </section>

        {/* ---------------------------------------------------------- 4 */}
        <section className="card">
          <h2>4. 病史 / 家族史 / 用药</h2>
          <Checks items={sex === "female" ? FEMALE_HISTORY : MALE_HISTORY} state={history} set={(k, v) => setHistory({ ...history, [k]: v })} />
          {sex === "male" && (
            <div className="field"><label>睡眠呼吸暂停</label>
              <select value={sleepApnea} onChange={(e) => setSleepApnea(e.target.value)}>
                <option value="unknown">未筛查</option><option value="no">无</option><option value="treated">已治疗</option><option value="untreated">未治疗</option></select></div>
          )}
          <h3>家族史</h3>
          <Checks items={sex === "female" ? FAMILY : FAMILY.slice(3)} state={family} set={(k, v) => setFamily({ ...family, [k]: v })} />
          <h3>用药</h3>
          <Checks items={MEDS} state={meds} set={(k, v) => setMeds({ ...meds, [k]: v })} />
          <div className="field"><label>当前/既往激素治疗及反应</label><input style={{ width: "100%" }} value={currentHrt} onChange={(e) => setCurrentHrt(e.target.value)} /></div>
        </section>

        {/* ---------------------------------------------------------- 5 */}
        <section className="card">
          <h2>5. 检验结果</h2>
          <div className="field"><label>默认采样日期（未单独填写的项目使用此日期）</label>
            <input type="date" value={labDate} onChange={(e) => setLabDate(e.target.value)} /></div>
          <p className="muted">按 DKi BHRT 体检套餐（{panelLabs.length} 项）排列；标 ★ 为处方决策必查项。</p>
          {panelCats.map((cat) => (
            <details key={cat} open={["血脂", "血糖", "肾功能", "肝功能", "甲状腺八项", "性激素", "其它激素", "肿瘤标记物"].includes(cat)}>
              <summary><strong>{cat}</strong>（{panelLabs.filter((p) => p.category === cat && p.codes.some((c) => labs[c]?.value)).length}/{panelLabs.filter((p) => p.category === cat).length}）</summary>
              <div className="table-wrap"><table><tbody>
                {panelLabs.filter((p) => p.category === cat).flatMap((p) => p.codes.map((code, idx) => {
                  const a = analyte(code);
                  const row = labs[code];
                  const set = (patch: Partial<LabRow>) => setLabs({ ...labs, [code]: { ...row, ...patch } });
                  return (
                    <tr key={code}>
                      <td style={{ width: "45%" }}>{idx === 0 ? `${p.no}. ` : "　 或 "}{a.name_zh}{CRITICAL.has(code) ? " ★" : ""}</td>
                      <td>{a.qualitative
                        ? <select value={row.value} onChange={(e) => set({ value: e.target.value })}>
                            <option value="">—</option><option value="0">阴性</option><option value="1">阳性</option></select>
                        : <input inputMode="decimal" size={7} value={row.value} onChange={(e) => set({ value: e.target.value })} />}</td>
                      <td>{a.free_unit || a.qualitative ? <span className="muted">{a.canonical_unit}</span>
                        : <select value={row.unit} onChange={(e) => set({ unit: e.target.value })}>
                            {a.units.map((u) => <option key={u}>{u}</option>)}</select>}</td>
                      <td><input type="date" value={row.date} onChange={(e) => set({ date: e.target.value })} /></td>
                    </tr>
                  );
                }))}
              </tbody></table></div>
            </details>
          ))}
          {sex === "male" && (
            <div className="row" style={{ marginTop: 12 }}>
              <div className="field"><label>第二次晨起总睾酮</label><input inputMode="decimal" size={7} value={tRepeat.value} onChange={(e) => setTRepeat({ ...tRepeat, value: e.target.value })} /></div>
              <div className="field"><label>单位</label><select value={tRepeat.unit} onChange={(e) => setTRepeat({ ...tRepeat, unit: e.target.value })}>
                <option>nmol/L</option><option>ng/dL</option><option>ng/mL</option></select></div>
            </div>
          )}
        </section>

        {/* ---------------------------------------------------------- 6 */}
        {sex === "female" && (
          <section className="card">
            <h2>6. 影像</h2>
            <div className="row">
              <div className="field"><label>乳腺检查日期</label><input type="date" value={breast.date} onChange={(e) => setBreast({ ...breast, date: e.target.value })} /></div>
              <div className="field"><label>方式</label><select value={breast.modality} onChange={(e) => setBreast({ ...breast, modality: e.target.value })}>
                <option value="ultrasound">乳腺超声</option><option value="mammogram">钼靶</option><option value="both">两者</option></select></div>
              <div className="field"><label>BI-RADS</label><select value={breast.birads} onChange={(e) => setBreast({ ...breast, birads: e.target.value })}>
                <option value="">未做</option>{[0, 1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
            </div>
            <div className="row">
              <div className="field"><label>经阴道超声日期</label><input type="date" value={tvus.date} onChange={(e) => setTvus({ ...tvus, date: e.target.value })} /></div>
              <div className="field"><label>内膜厚度 mm</label><input inputMode="decimal" size={5} value={tvus.thickness} onChange={(e) => setTvus({ ...tvus, thickness: e.target.value })} /></div>
              <label className="check"><input type="checkbox" checked={tvus.fibroids} onChange={(e) => setTvus({ ...tvus, fibroids: e.target.checked })} /> 超声见肌瘤</label>
              <div className="field"><label>DEXA T 值</label><input inputMode="decimal" size={5} value={dexa} onChange={(e) => setDexa(e.target.value)} /></div>
            </div>
          </section>
        )}
        <section className="card">
          <h3>套餐影像检查（已完成请勾选）</h3>
          <div className="checks">
            {panelImaging.map((p) => (
              <label key={p.imaging_code} className="check"><input type="checkbox" checked={!!imagingDone[p.imaging_code!]}
                onChange={(e) => setImagingDone({ ...imagingDone, [p.imaging_code!]: e.target.checked })} /> {p.no}. {p.name}</label>
            ))}
          </div>
          <p className="muted">乳腺、子宫卵巢、骨密度：填写上方具体结果后自动视为已完成。</p>
        </section>

        {/* ---------------------------------------------------------- 7 */}
        <section className="card">
          <h2>{sex === "female" ? "7" : "6"}. 方案偏好</h2>
          <div className="row">
            <div className="field"><label>给药途径偏好</label><select value={prefs.route} onChange={(e) => setPrefs({ ...prefs, route: e.target.value })}>
              <option value="no_preference">无偏好</option><option value="cream">经皮乳膏</option><option value="pellet">Pellet 皮下植入</option></select></div>
            {sex === "female" && (
              <div className="field"><label>黄体酮途径</label><select value={prefs.progesterone} onChange={(e) => setPrefs({ ...prefs, progesterone: e.target.value })}>
                <option value="auto">自动（睡眠→口服；肌瘤→阴道）</option><option value="oral">口服微粒化</option>
                <option value="vaginal">阴道</option><option value="cream">经皮乳膏（偏离默认）</option></select></div>
            )}
            {sex === "female" && (
              <div className="field"><label>双雌配比</label><select value={prefs.biest} onChange={(e) => setPrefs({ ...prefs, biest: e.target.value })}>
                <option value="2:8">Biest (2:8)</option><option value="1:9">Biest (1:9)</option></select></div>
            )}
            <div className="field"><label>开始日期</label><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
          </div>
          <div className="checks">
            {sex === "female" && (
              <label className="check"><input type="checkbox" checked={prefs.supplement} onChange={(e) => setPrefs({ ...prefs, supplement: e.target.checked })} /> 加用黄体酮乳膏作为补充（不替代内膜保护）</label>
            )}
            <label className="check"><input type="checkbox" checked={prefs.poor} onChange={(e) => setPrefs({ ...prefs, poor: e.target.checked })} /> 每日涂抹依从性差</label>
            <label className="check"><input type="checkbox" checked={prefs.consent} onChange={(e) => setPrefs({ ...prefs, consent: e.target.checked })} /> 已签署 Pellet 知情同意</label>
          </div>
        </section>

        {error && <div className="alert error" role="alert">{error}</div>}
        <button type="submit" disabled={busy}>{busy ? "处理中…" : "核查并生成处方草案"}</button>
      </form>

      {result && <ResultView ev={result} catalog={catalog} identity={identity} />}
    </>
  );
}

const LEVEL_LABEL: Record<string, string> = { STOP: "禁忌", HOLD: "暂缓", CAUTION: "注意", INFO: "提示" };

function ResultView({ ev, catalog, identity }: { ev: Evaluation; catalog: BhrtCatalog; identity: PatientIdentity }) {
  const required = ev.missing.filter((m) => m.required);
  const optional = ev.missing.filter((m) => !m.required && m.category !== "package");
  const pkg = ev.missing.filter((m) => !m.required && m.category === "package");
  const flagged = ev.labs.filter((l) => l.flag !== "normal");
  const cls = ev.status === "draft" ? "ok" : ev.status === "incomplete" ? "warn" : "error";
  return (
    <div id="result" style={{ marginTop: 24 }}>
      <div className="no-print">
        <h2>评估结果</h2>
        <div className={`alert ${cls}`}><strong>{ev.status_label}</strong>　闸门：{ev.gate}　分期：{ev.stage.label}</div>

        {(required.length > 0 || optional.length > 0 || pkg.length > 0) && (
          <section className="card">
            <h3>报告核查：缺项清单</h3>
            {required.length > 0 && <><p className="err">必须补充（{required.length}）</p>
              <ul>{required.map((m) => <li key={m.item}>{m.item} <span className="muted">— {m.reason}</span></li>)}</ul></>}
            {optional.length > 0 && <><p className="muted">建议补充（{optional.length}）</p>
              <ul className="muted">{optional.map((m) => <li key={m.item}>{m.item}</li>)}</ul></>}
            {pkg.length > 0 && <details><summary>BHRT 体检套餐缺项（{pkg.length}，不影响处方生成）</summary>
              <ul className="muted cols">{pkg.map((m) => <li key={m.item}>{m.item}</li>)}</ul></details>}
          </section>
        )}
        {ev.lab_errors.length > 0 && <div className="alert warn">{ev.lab_errors.map((e) => <div key={e}>{e}</div>)}</div>}

        <section className="card">
          <h3>风险分析</h3>
          {ev.risks.length === 0 ? <p className="muted">未发现风险点</p> : (
            <div className="table-wrap"><table>
              <thead><tr><th>级别</th><th>风险点</th><th>依据</th><th>处理</th></tr></thead>
              <tbody>{ev.risks.map((r) => (
                <tr key={r.code}><td><span className={`badge lvl-${r.level}`}>{LEVEL_LABEL[r.level]}{r.scope === "pellet" ? "·Pellet" : r.scope === "testosterone" ? "·睾酮" : ""}</span></td>
                  <td>{r.title}</td><td>{r.detail}</td><td>{r.action}</td></tr>))}</tbody>
            </table></div>
          )}
          {flagged.length > 0 && (<>
            <h3>异常指标</h3>
            <ul>{flagged.map((l) => <li key={l.code}>{l.name_zh}: {l.display}（{l.note}）</li>)}</ul>
          </>)}
          {ev.symptoms.map.length > 0 && (<>
            <h3>症状 → 激素对应</h3>
            <div className="table-wrap"><table>
              <thead><tr><th>症状</th><th>主要手段</th><th>先排查</th></tr></thead>
              <tbody>{ev.symptoms.map.map((m) => <tr key={m.symptom}><td>{m.symptom}</td><td>{m.lever}</td><td>{m.check_first}</td></tr>)}</tbody>
            </table></div>
          </>)}
          {ev.referrals.length > 0 && (<><h3>转诊 / 进一步检查</h3><ul>{ev.referrals.map((r) => <li key={r}>{r}</li>)}</ul></>)}
        </section>
      </div>

      {ev.status === "draft" && <Prescription ev={ev} catalog={catalog} identity={identity} />}
    </div>
  );
}
