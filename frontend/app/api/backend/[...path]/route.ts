// Same-origin proxy to the FastAPI backend. The bearer token stays on the
// server (never shipped to the browser). Bodies are forwarded, never logged.
import { NextRequest, NextResponse } from "next/server";

const BASE = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
const SEGMENT = /^[A-Za-z0-9_-]{1,64}$/;
const ALLOWED_ROOTS = new Set(["patients", "bioage", "bhrt"]);

async function forward(req: NextRequest, path: string[], method: "GET" | "POST") {
  if (!path.length || !ALLOWED_ROOTS.has(path[0]) || !path.every((p) => SEGMENT.test(p))) {
    return NextResponse.json({ status: "error", code: "NOT_FOUND", message: "not found" }, { status: 404 });
  }
  const token = process.env.BACKEND_API_TOKEN;
  if (!token) {
    return NextResponse.json(
      { status: "error", code: "MISCONFIGURED", message: "BACKEND_API_TOKEN 未配置" },
      { status: 500 },
    );
  }
  const res = await fetch(`${BASE}/api/v1/${path.join("/")}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: method === "POST" ? await req.text() : undefined,
    cache: "no-store",
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path, "GET");
}

export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path, "POST");
}
