import type { ExtractResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function extractInvoices(files: File[]): Promise<ExtractResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));

  const resp = await fetch(`${API_BASE}/api/extract`, {
    method: "POST",
    body: form,
  });

  if (!resp.ok) {
    let detail = `Server returned ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return (await resp.json()) as ExtractResponse;
}
