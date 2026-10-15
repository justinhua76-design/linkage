import Link from "next/link";
import { notFound } from "next/navigation";
import { BackendError, backendGet } from "@/lib/server-api";
import { BIOMARKER_ORDER, fmt, fmtDateTime, QUALITY_LABEL } from "@/lib/format";
import type { Catalog, Overview } from "@/lib/types";

export const dynamic = "force-dynamic";

const SOURCE_LABEL: Record<string, string> = {
  manual_entry: "手工录入",
  lab_import: "实验室导入",
  synthetic: "合成数据",
};

export default async function OverviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let ov: Overview;
  try {
    ov = await backendGet<Overview>(`/patients/${id}/overview`);
  } catch (e) {
    if (e instanceof BackendError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  const catalog = await backendGet<Catalog>("/bioage/biomarkers");
  const name = (c: string) => catalog.biomarkers.find((b) => b.code === c)?.name_zh ?? c;
  const p = ov.patient;

  return (
    <>
      <h1>指标概览 · {p.pseudonym}</h1>
      <div className="card">
        <dl className="kv">
          <dt>性别</dt><dd>{p.sex}</dd>
          <dt>出生日期</dt><dd>{p.birth_date ?? "—"}</dd>
          <dt>合成数据</dt><dd>{p.is_synthetic ? "是" : "否"}</dd>
        </dl>
        <p className="row" style={{ marginTop: 12 }}>
          <Link className="btn-link" href={`/patients/${p.id}/labs/new`}>录入指标</Link>
        </p>
      </div>

      <h2>最新指标</h2>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>指标</th><th>结果</th><th>单位</th><th>模型单位值</th><th>参考范围</th><th>检测日期</th><th>来源</th><th>质量状态</th></tr>
          </thead>
          <tbody>
            {BIOMARKER_ORDER.map((code) => {
              const l = ov.latest_labs[code];
              if (!l) {
                return (
                  <tr key={code}>
                    <td>{name(code)}</td>
                    <td colSpan={6} className="muted">暂无数据</td>
                    <td><span className="badge flag">{QUALITY_LABEL.missing}</span></td>
                  </tr>
                );
              }
              return (
                <tr key={code}>
                  <td>{name(code)}</td>
                  <td>{l.below_lod ? `< ${fmt(l.lod_original, 4)}` : fmt(l.value_original, 4)}</td>
                  <td>{l.unit_original}</td>
                  <td>{l.below_lod ? "—" : `${fmt(l.value_canonical, 4)} ${l.unit_canonical}`}</td>
                  <td>
                    {fmt(l.reference_low, 3)}–{fmt(l.reference_high, 3)} {l.reference_unit}
                    <div className="muted">{l.reference_source === "lab" ? "实验室提供" : "系统通用"}</div>
                  </td>
                  <td>{l.collected_on}</td>
                  <td>{SOURCE_LABEL[l.source] ?? l.source}</td>
                  <td>
                    <span className={`badge ${l.quality_status === "valid" ? "valid" : "flag"}`}>
                      {QUALITY_LABEL[l.quality_status] ?? l.quality_status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2>PhenoAge 计算历史</h2>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>计算时间</th><th>实际年龄</th><th>PhenoAge</th><th>模型版本</th><th /></tr>
          </thead>
          <tbody>
            {ov.results.length === 0 && <tr><td colSpan={5} className="muted">暂无计算结果</td></tr>}
            {ov.results.map((r) => (
              <tr key={r.id}>
                <td>{fmtDateTime(r.computed_at)}</td>
                <td>{fmt(r.chronological_age, 1)}</td>
                <td>{r.phenoage.toFixed(1)}</td>
                <td>{r.model_id} v{r.model_version}</td>
                <td><Link href={`/patients/${p.id}/results/${r.id}`}>详情</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">共 {ov.labs.length} 条检测记录。</p>
    </>
  );
}
