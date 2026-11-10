import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "uSciTec BioAge AI",
  description: "Deterministic PhenoAge research tool (research use only)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="top">
          <span className="brand">uSciTec BioAge AI</span>
          <nav className="row">
            <Link href="/">患者列表</Link>
            <Link href="/patients/new">新建患者</Link>
            <Link href="/bhrt">BHRT 处方</Link>
          </nav>
        </header>
        <div className="ruo" role="note">
          仅供研究和内部验证使用（Research Use Only）。结果来自确定性算法引擎（Levine 2018 PhenoAge），
          不构成疾病诊断或治疗建议。请仅使用合成或已脱敏数据。
        </div>
        <main>{children}</main>
      </body>
    </html>
  );
}
