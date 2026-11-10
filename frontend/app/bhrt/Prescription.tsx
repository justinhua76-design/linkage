"use client";

import type { BhrtCatalog, Evaluation, PatientIdentity, RxItem } from "@/lib/bhrt";

const CLINIC = "DKi";
const STAGES: [string, string][] = [
  ["A", "围绝经期"], ["B", "绝经早期(<10年)"], ["C", "绝经晚期(≥10年/≥60岁)"], ["D", "手术绝经/POI"], ["M", "男性性腺功能减退"],
];
const box = (on: boolean) => (on ? "☑" : "☐");

function containers(x: RxItem): number {
  const m = /×\s*(\d+)/.exec(x.duration_quantity);
  return m ? Number(m[1]) : 1;
}

function note(x: RxItem): string {
  const i = x.duration_quantity.indexOf("；");
  return i >= 0 ? x.duration_quantity.slice(i + 1) : "";
}

export default function Prescription({ ev, catalog, identity }: {
  ev: Evaluation; catalog: BhrtCatalog; identity: PatientIdentity;
}) {
  const s = ev.symptoms;
  const today = new Date().toISOString().slice(0, 10);
  const formProducts = catalog.products.filter((p) => p.on_form);
  const byCode = new Map(ev.prescription.map((x) => [x.product_code, x]));
  const onForm = ev.prescription.filter((x) => formProducts.some((p) => p.code === x.product_code));
  const other = ev.prescription.filter((x) => !formProducts.some((p) => p.code === x.product_code));
  const blank = (v: string) => v || "________________";

  return (
    <article className="rx-doc card">
      <div className="row between no-print" style={{ marginBottom: 12 }}>
        <strong>处方单（可打印 / 另存为 PDF）</strong>
        <button type="button" onClick={() => window.print()}>打印 / 导出 PDF</button>
      </div>

      {/* =============================================================== page 1: DKi form */}
      <section className="rx-form">
        <div className="rx-clinic">{CLINIC}</div>
        <h1 className="rx-title">Bioidentical Hormone Replacement Therapy (BHRT)<br />Prescription Form / 生物同源性荷尔蒙处方</h1>
        <p className="rx-draft">【草案——须经执业医师审核签字后方可生效】</p>

        <h2 className="rx-center">Patient Information / 患者资料</h2>
        <div className="rx-info">
          <span>Patient Name / 患者姓名</span><span className="rx-line">{blank(identity.name)}</span>
          <span>Date / 日期</span><span className="rx-line">{today}</span>
          <span>Doctor / 医师</span><span className="rx-line">{blank(identity.doctor)}</span>
          <span>Address / 住址</span><span className="rx-line">{blank(identity.address)}</span>
          <span>Patient ID / 病历号</span><span className="rx-line">{blank(identity.patientId || ev.client_ref)}</span>
          <span>Tel / 电话</span><span className="rx-line">{blank(identity.tel)}</span>
        </div>

        <h2 className="rx-center">Hormone Selection / 荷尔蒙选择</h2>
        <table className="rx-table rx-select">
          <thead><tr><th>Hormone 激素</th><th>Strength (mg/mL)</th><th>Equivalent (%)</th><th>Tick ✓</th></tr></thead>
          <tbody>
            {formProducts.map((p, k) => {
              const first = k === 0 || formProducts[k - 1].hormone_en !== p.hormone_en;
              const label = p.hormone_en === p.hormone_zh || p.hormone_en.startsWith("Biest") ? p.hormone_en : `${p.hormone_en} ${p.hormone_zh}`;
              return (
                <tr key={p.code} className={byCode.has(p.code) ? "ticked" : ""}>
                  <td>{first ? label : ""}</td><td>{p.strength}</td><td>{p.equivalent}</td>
                  <td className="rx-tick">{box(byCode.has(p.code))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <h2>Prescription Details / 处方资料</h2>
        {onForm.length === 0 && <p className="muted">（无乳膏处方）</p>}
        {onForm.map((x) => {
          const n = containers(x);
          const p = formProducts.find((q) => q.code === x.product_code)!;
          return (
            <div key={x.product_code} className="rx-detail">
              <div className="rx-detail-title">{p.hormone_en} {p.hormone_zh !== p.hormone_en ? p.hormone_zh : ""} · {p.equivalent}（{p.strength}）</div>
              <div>Quantity / 数量：{box(n === 1)} 30 mL　{box(n > 1)} Other：{n > 1 ? `30 mL × ${n}` : "________"}</div>
              <div>Dose / 剂量：{x.dose}（{x.active_dose}）</div>
              <div>Directions / 用法：{x.frequency}{note(x) ? `；${note(x)}` : ""}</div>
              <div>Application Site / 涂抹部位：{x.route_site}</div>
              <div className="muted">目的：{x.purpose}</div>
            </div>
          );
        })}
        {other.length > 0 && (<>
          <h3>Other / 其他（非乳膏）</h3>
          <table className="rx-table"><thead><tr><th>药品</th><th>规格</th><th>剂量</th><th>用法 / 部位</th><th>频次</th><th>数量</th></tr></thead>
            <tbody>{other.map((x) => (
              <tr key={x.product_code}><td>{x.product_name}</td><td>{x.strength}</td><td>{x.dose}（{x.active_dose}）</td>
                <td>{x.route_site}</td><td>{x.frequency}</td><td>{x.duration_quantity}</td></tr>))}</tbody>
          </table>
        </>)}

        <h2>General Instructions / 使用说明</h2>
        {catalog.form_instructions.map((g) => <p key={g.en} className="rx-gi">{g.en} / {g.zh}</p>)}
        <p className="rx-gi">1 转 = 250 mg = 0.25 mL（Topi-Click）</p>

        <p className="rx-sign">Doctor Signature / 医师签名：____________________　　Date / 日期：______________</p>
      </section>

      {/* =============================================================== page 2: clinical summary */}
      <section className="rx-clinical">
        <div className="rx-clinic">{CLINIC}</div>
        <h1 className="rx-title">BHRT 临床评估与随访计划</h1>
        <p className="rx-center muted">患者：{identity.name || ev.client_ref}　病历号：{identity.patientId || ev.client_ref}　日期：{today}</p>

        <h2>一、客户信息</h2>
        <p>性别：{ev.sex === "female" ? "女" : "男"}　年龄：{ev.age}　BMI：{ev.bmi ?? "待补"}　血压：{ev.bp ?? "待补"}</p>
        <p>分期：{STAGES.map(([c, l]) => `${box(ev.stage.code === c)}${l}`).join("　")}</p>
        <p className="muted">{ev.stage.implication}</p>

        <h2>二、安全闸门结果</h2>
        <p>结论：{box(ev.gate === "PROCEED" || ev.gate === "CAUTION")}可进行{ev.gate === "CAUTION" ? "（需注意）" : ""}　{box(ev.gate === "HOLD")}暂缓　{box(ev.gate === "STOP")}禁忌</p>
        {ev.risks.length > 0 && <ul>{ev.risks.map((r) => <li key={r.code}>[{r.level}] {r.title}：{r.action}</li>)}</ul>}

        <h2>三、主要症状与评分</h2>
        {s.scale === "MRS"
          ? <p>MRS 总分：{s.total}（{s.severity}）　躯体 {s.somatic} / 心理 {s.psychological} / 泌尿生殖 {s.urogenital}<br />主要诉求：{(s.top_complaints ?? []).join("、") || "—"}</p>
          : <p>ADAM：{s.positive ? "阳性" : "阴性"}（{s.yes_count}/10）　{(s.items ?? []).join("、")}</p>}

        <h2>四、给药途径及子宫内膜保护</h2>
        <p>{box(ev.route.selected === "cream")}经皮乳膏　{box(ev.route.selected === "pellet")}Pellet 皮下植入</p>
        <ul>{ev.route.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        <p>子宫内膜保护：{ev.endometrial_protection || "—"}</p>

        <h2>五、客户注意事项</h2>
        <ul>{ev.client_instructions.map((t) => <li key={t}>{t}</li>)}</ul>

        <h2>六、复诊与检测计划</h2>
        <table className="rx-table"><tbody>
          {ev.monitoring.map((f) => <tr key={f.when + f.label}><td style={{ whiteSpace: "nowrap" }}>{f.when}</td><td>{f.label}</td><td>{f.items.join("；")}</td></tr>)}
        </tbody></table>

        <h2>七、预期变化（仅供参考）</h2>
        <ul>{ev.expected_outcomes.map((o) => <li key={o.domain}>{o.domain}：一般 {o.onset} 起（记录：{o.track}）</li>)}</ul>
        <p className="muted">注：个体反应差异显著，以上时间为一般观察，不构成疗效承诺。</p>

        <h2>八、医师审核</h2>
        <p>审核意见 / 修改：</p>
        <div className="rx-sign-lines"><div /><div /></div>
        <p className="rx-sign">执业医师签名：__________　执业证号：__________　日期：__________</p>

        <div className="rx-notes">
          <strong>临床备注（内部）</strong>
          {ev.deviations.length > 0 && <><div>偏离默认规则：</div><ul>{ev.deviations.map((d) => <li key={d}>{d}</li>)}</ul></>}
          {ev.assumptions.length > 0 && <><div>假设：</div><ul>{ev.assumptions.map((d) => <li key={d}>{d}</li>)}</ul></>}
          {ev.pending.length > 0 && <><div>待医师决定：</div><ul>{ev.pending.map((d) => <li key={d}>{d}</li>)}</ul></>}
          <p className="muted">引擎版本 {ev.engine_version}　生成日期 {today}</p>
        </div>
      </section>
    </article>
  );
}
