// Server-side only: talks to the FastAPI backend with the server-held token.
import "server-only";

const BASE = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class BackendError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`backend responded ${status}`);
  }
}

export async function backendGet<T>(path: string): Promise<T> {
  const token = process.env.BACKEND_API_TOKEN;
  if (!token) throw new Error("BACKEND_API_TOKEN is not configured");
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new BackendError(res.status, body);
  return body as T;
}
