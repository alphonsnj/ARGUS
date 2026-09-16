export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type CurrentUser = {
  id: string;
  email: string;
  is_active: boolean;
  mfa_enabled: boolean;
  created_at: string;
  roles: string[];
};

export type DocumentEntity = { kind: string; value: string };

export type InvestigationDocument = {
  id: string;
  original_filename: string;
  content_type: string;
  byte_size: number;
  sha256: string;
  status: "queued" | "processing" | "ready" | "rejected" | "failed";
  extracted_metadata: Record<string, unknown> | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
  entities: DocumentEntity[];
};

async function refreshAccessToken(): Promise<string | null> {
  const response = await fetch(`${apiUrl}/auth/refresh`, { method: "POST", credentials: "include" });
  if (!response.ok) return null;
  const payload: { access_token: string } = await response.json();
  sessionStorage.setItem("argus_access_token", payload.access_token);
  return payload.access_token;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let token = sessionStorage.getItem("argus_access_token") ?? await refreshAccessToken();
  let response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (response.status === 401 && token) {
    token = await refreshAccessToken();
    if (token) {
      response = await fetch(`${apiUrl}${path}`, {
        ...init,
        credentials: "include",
        headers: { ...init.headers, Authorization: `Bearer ${token}` },
      });
    }
  }
  return response;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await apiFetch("/users/me");
  return response.ok ? response.json() : null;
}
