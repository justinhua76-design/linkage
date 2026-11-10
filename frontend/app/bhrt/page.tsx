import { backendGet } from "@/lib/server-api";
import type { BhrtCatalog } from "@/lib/bhrt";
import BhrtWorkbench from "./BhrtWorkbench";

export const dynamic = "force-dynamic";

export default async function BhrtPage() {
  let catalog: BhrtCatalog | null = null;
  try {
    catalog = await backendGet<BhrtCatalog>("/bhrt/catalog");
  } catch {
    catalog = null;
  }
  return (
    <>
      <h1 className="no-print">BHRT 处方工具</h1>
      <p className="muted no-print">
        导入报告 → 核查缺项 → 风险分析 → 生成处方草案。草案须经执业医师审核签字后方可生效。
      </p>
      {catalog ? <BhrtWorkbench catalog={catalog} /> : <div className="alert error">无法连接后端服务</div>}
    </>
  );
}
