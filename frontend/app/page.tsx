import Link from "next/link";
import { backendGet } from "@/lib/server-api";
import type { Patient } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Home() {
  let patients: Patient[] = [];
  let error: string | null = null;
  try {
    patients = await backendGet<Patient[]>("/patients");
  } catch {
    error = "无法连接后端服务";
  }
  return (
    <>
      <h1>患者列表</h1>
      <p>
        <Link className="btn-link" href="/patients/new">+ 新建患者</Link>
      </p>
      {error && <div className="alert error">{error}</div>}
      <div className="card table-wrap">
        <table>
          <thead>
            <tr><th>研究编号</th><th>性别</th><th>合成数据</th><th>创建时间</th><th /></tr>
          </thead>
          <tbody>
            {patients.length === 0 && (
              <tr><td colSpan={5} className="muted">暂无患者</td></tr>
            )}
            {patients.map((p) => (
              <tr key={p.id}>
                <td>{p.pseudonym}</td>
                <td>{p.sex}</td>
                <td>{p.is_synthetic ? "是" : "否"}</td>
                <td>{p.created_at.slice(0, 10)}</td>
                <td><Link href={`/patients/${p.id}`}>指标概览</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
