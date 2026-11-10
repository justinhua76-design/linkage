"use client";

import type { Evaluation } from "@/lib/bhrt";

const STAGES: [string, string][] = [
  ["A", "围绝经期"], ["B", "绝经早期(<10年)"], ["C", "绝经晚期(≥10年/≥60岁)"], ["D", "手术绝经/POI"], ["M", "男性性腺功能减退"],
];
const box = (on: boolean) => (on ? "☑" : "☐");

export default function Prescription({ ev }: { ev: Evaluation }) {
  const s = ev.symptoms;
  const today = new Date().toISOString().slice(0, 10);
  return (
    <article className="rx-doc card">
      <div className="row between no-print" style={{ marginBottom: 12 }}>
        <strong>处方单（可打印 / 另存为 PDF）</strong>
        <button type="button" onClick={() => window.print()}>打印 / 导出 PDF</button>
      </div>

      <h1 className="rx-title">生物同源荷尔蒙替代疗法（BHRT）处方草案</h1>
      <p className="rx-draft">【草案——须经执业医师审核签字后方可生效】</p>

      <h2>一、客户信息</h2>
      <p>
        编号：{ev.client_ref}　性别：{ev.sex === "female" ? "女" : "男"}　年龄：{ev.age}　BMI：{ev.bmi ?? "待补"}　血压：{ev.bp ?? "待补"}
      </p>
      <p>分期：{STAGES.map(([c, l]) => `${box(ev.stage.code === c)}${l}`).join("　")}</p>
      <p className="muted">{ev.stage.implication}</p>

      <h2>二、安全闸门结果</h2>
      <p>结论：{box(ev.gate === "PROCEED" || ev.gate === "CAUTION")}可进行{ev.gate === "CAUTION" ? "（需注意）" : ""}　{box(ev.gate === "HOLD")}暂缓　{box(ev.gate === "STOP")}禁忌</p>
      {ev.risks.length > 0 && <ul>{ev.risks.map((r) => <li key={r.code}>[{r.level}] {r.title}：{r.action}</li>)}</ul>}

      <h2>三、主要症状与评分</h2>
      {s.scale === "MRS"
        ? <p>MRS 总分：{s.total}（{s.severity}）　躯体 {s.somatic} / 心理 {s.psychological} / 泌尿生殖 {s.urogenital}<br />主要诉求：{(s.top_complaints ?? []).join("、") || "—"}</p>
        : <p>ADAM：{s.positive ? "阳性" : "阴性"}（{s.yes_count}/10）　{(s.items ?? []).join("、")}</p>}

      <h2>四、给药途径选择及理由</h2>
      <p>{box(ev.route.selected === "cream")}经皮乳膏　{box(ev.route.selected === "pellet")}Pellet 皮下植入</p>
      <ul>{ev.route.reasons.map((r) => <li key={r}>{r}</li>)}</ul>

      <h2>五、处方明细</h2>
      {ev.prescription.length === 0 ? <p>当前症状未达用药指征，建议 3 个月后复评。</p> : (
        <div className="table-wrap"><table className="rx-table">
          <thead><tr><th>药品</th><th>规格</th><th>剂量</th><th>有效成分</th><th>用法 / 部位</th><th>频次</th><th>疗程 / 数量</th><th>目的</th></tr></thead>
          <tbody>{ev.prescription.map((x) => (
            <tr key={x.product_code} className={x.pending_spec ? "pending" : ""}>
              <td>{x.product_name}</td><td>{x.strength}</td><td>{x.dose}</td><td>{x.active_dose}</td>
              <td>{x.route_site}</td><td>{x.frequency}</td><td>{x.duration_quantity}</td><td>{x.purpose}</td>
            </tr>))}</tbody>
        </table></div>
      )}
      <p>子宫内膜保护方案：{ev.endometrial_protection || "—"}</p>

      <h2>六、使用说明（客户版）</h2>
      <ul>{ev.client_instructions.map((t) => <li key={t}>{t}</li>)}</ul>

      <h2>七、复诊与检测计划</h2>
      <table className="rx-table"><tbody>
        {ev.monitoring.map((f) => <tr key={f.when + f.label}><td style={{ whiteSpace: "nowrap" }}>{f.when}</td><td>{f.label}</td><td>{f.items.join("；")}</td></tr>)}
      </tbody></table>

      <h2>八、预期变化（仅供参考）</h2>
      <ul>{ev.expected_outcomes.map((o) => <li key={o.domain}>{o.domain}：一般 {o.onset} 起（记录：{o.track}）</li>)}</ul>
      <p className="muted">注：个体反应差异显著，以上时间为一般观察，不构成疗效承诺。</p>

      <h2>九、医师审核</h2>
      <p>审核意见 / 修改：</p>
      <div className="rx-sign-lines"><div /><div /></div>
      <p className="rx-sign">执业医师签名：__________　执业证号：__________　日期：__________</p>

      <section className="rx-notes">
        <h2>临床备注（内部）</h2>
        {ev.deviations.length > 0 && <><strong>偏离默认规则：</strong><ul>{ev.deviations.map((d) => <li key={d}>{d}</li>)}</ul></>}
        {ev.assumptions.length > 0 && <><strong>假设：</strong><ul>{ev.assumptions.map((d) => <li key={d}>{d}</li>)}</ul></>}
        {ev.pending.length > 0 && <><strong>待补 / 待确认：</strong><ul>{ev.pending.map((d) => <li key={d}>{d}</li>)}</ul></>}
        {ev.missing.length > 0 && <><strong>建议补充检查：</strong> {ev.missing.map((m) => m.item).join("、")}</>}
        <p className="muted">引擎版本 {ev.engine_version}　生成日期 {today}</p>
      </section>
    </article>
  );
}
