import Link from "next/link";
import { notFound } from "next/navigation";
import { BackendError, backendGet } from "@/lib/server-api";
import { fmt, fmtDateTime, QUALITY_LABEL } from "@/lib/format";
import type { BiomarkerMeta, Catalog, PhenoAgeResult } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ResultPage({ params }: { params: Promise<{ id: string; resultId: string }> }) {
  const { id, resultId } = await params;
  let r: PhenoAgeResult;
  try {
    r = await backendGet<PhenoAgeResult>(`/bioage/results/${resultId}`);
  } catch (e) {
    if (e instanceof BackendError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  if (r.patient_id !== id) notFound();
  const catalog = await backendGet<Catalog>("/bioage/biomarkers");
  const meta = (code: string): BiomarkerMeta | undefined => catalog.biomarkers.find((b) => b.code === code);
  const diff = r.phenoage_minus_chronological_age;

  return (
    <>
      <h1>计算结果</h1>
      <div className="card">
        <div className="row" style={{ gap: 32 }}>
          <div>
            <div className="muted">PhenoAge（表型年龄）</div>
            <div className="big" data-testid="phenoage">{r.phenoage_rounded.toFixed(1)}</div>
            <div className="muted">岁</div>
          </div>
          <div>
            <div className="muted">实际年龄</div>
            <div className="big">{fmt(r.chronological_age, 1)}</div>
            <div className="muted">岁</div>
          </div>
          <div>
            <div className="muted">PhenoAge − 实际年龄</div>
            <div className="big">{diff >= 0 ? "+" : ""}{diff.toFixed(1)}</div>
            <div className="muted">岁（未经校准的差值，非 PhenoAgeAccel 残差）</div>
          </div>
        </div>
        <p className="muted">
          模型 10 年（120 个月）死亡风险评分 M = {(r.mortality_score * 100).toFixed(2)}%（模型内部量，非个体诊断）。
        </p>
      </div>

      {r.warnings.length > 0 && (
        <div className="alert warn" role="status">
          <strong>数据质量提示</strong>
          {r.warnings.map((w) => <div key={w.code + w.field}>· {w.message}</div>)}
        </div>
      )}

      <h2>输入指标与单位换算</h2>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>指标</th><th>录入值</th><th>录入单位</th><th>换算系数</th><th>模型值</th><th>模型单位</th><th>质量状态</th></tr>
          </thead>
          <tbody>
            {r.inputs.map((m) => (
              <tr key={m.code}>
                <td>{meta(m.code)?.name_zh ?? m.code}</td>
                <td>{m.below_lod ? "< LOD" : fmt(m.original_value, 4)}</td>
                <td>{m.original_unit}</td>
                <td>{fmt(m.conversion_factor, 5)}</td>
                <td>{fmt(m.canonical_value, 4)}</td>
                <td>{m.canonical_unit}</td>
                <td>
                  <span className={`badge ${m.quality_status === "valid" ? "valid" : "flag"}`}>
                    {QUALITY_LABEL[m.quality_status] ?? m.quality_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>可追溯信息</h2>
      <div className="card">
        <dl className="kv">
          <dt>模型</dt><dd>{r.model.model_id} v{r.model.model_version}</dd>
          <dt>引擎版本</dt><dd>{r.model.engine_version}</dd>
          <dt>系数指纹 (SHA-256)</dt><dd><code>{r.model.coefficients_sha256}</code></dd>
          <dt>算法来源</dt><dd>{r.model.algorithm_source}</dd>
          <dt>计算时间</dt><dd>{fmtDateTime(r.computed_at)}</dd>
          <dt>CRP 检出限策略</dt><dd>{r.lod_policy}</dd>
          <dt>结果 ID</dt><dd><code>{r.result_id}</code></dd>
        </dl>
        <p className="muted">{r.disclaimer}</p>
      </div>
      <p className="row">
        <Link className="btn-link" href={`/patients/${id}`}>查看指标概览</Link>
        <Link className="btn-link" href={`/patients/${id}/labs/new`}>录入新一组指标</Link>
      </p>
    </>
  );
}
