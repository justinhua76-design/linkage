"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ApiError, Patient } from "@/lib/types";

export default function NewPatientPage() {
  const router = useRouter();
  const [pseudonym, setPseudonym] = useState("");
  const [sex, setSex] = useState("unknown");
  const [birthDate, setBirthDate] = useState("");
  const [synthetic, setSynthetic] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErrors([]);
    if (!/^[A-Za-z0-9_-]{3,64}$/.test(pseudonym)) {
      setErrors(["研究编号须为 3–64 位字母、数字、- 或 _（请勿使用真实姓名或证件号）"]);
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/backend/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pseudonym,
          sex,
          birth_date: birthDate || null,
          is_synthetic: synthetic,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        const err = body as ApiError;
        setErrors(err.errors?.length ? err.errors.map((i) => `${i.field}: ${i.message}`) : [err.message]);
        return;
      }
      router.push(`/patients/${(body as Patient).id}/labs/new`);
    } catch {
      setErrors(["网络错误，请重试"]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>新建患者</h1>
      <form className="card" onSubmit={submit} noValidate>
        {errors.length > 0 && (
          <div className="alert error" role="alert">
            {errors.map((m) => <div key={m}>{m}</div>)}
          </div>
        )}
        <div className="field">
          <label htmlFor="pseudonym">研究编号（假名）</label>
          <input id="pseudonym" value={pseudonym} onChange={(e) => setPseudonym(e.target.value)}
                 placeholder="例如 SYN-0001" autoComplete="off" required />
          <div className="muted">禁止填写真实姓名、身份证号、手机号等可识别信息。</div>
        </div>
        <div className="row">
          <div className="field">
            <label htmlFor="sex">性别</label>
            <select id="sex" value={sex} onChange={(e) => setSex(e.target.value)}>
              <option value="female">女</option>
              <option value="male">男</option>
              <option value="other">其他</option>
              <option value="unknown">未知</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="birth_date">出生日期（可选，用于计算实际年龄）</label>
            <input id="birth_date" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>
            <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} />{" "}
            合成测试数据
          </label>
        </div>
        <button type="submit" disabled={busy}>{busy ? "保存中…" : "创建并录入指标"}</button>
      </form>
    </>
  );
}
