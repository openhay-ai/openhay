import { getApiBaseUrl } from "./api";

const TOKEN_KEY = "auth_token";

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // ignore storage errors
  }
}

export async function fetchGuestToken(): Promise<string> {
  const res = await fetch(`${getApiBaseUrl()}/api/auth/token/guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const data = (await res.json()) as { access_token?: string };
  const token = data?.access_token || "";
  if (!token) throw new Error("No token returned");
  setStoredToken(token);
  return token;
}

export async function fetchUserToken(identifier: string): Promise<string> {
  const res = await fetch(`${getApiBaseUrl()}/api/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier }),
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const data = (await res.json()) as { access_token?: string };
  const token = data?.access_token || "";
  if (!token) throw new Error("No token returned");
  setStoredToken(token);
  return token;
}

export async function ensureToken(): Promise<string> {
  const existing = getStoredToken();
  if (existing) return existing;
  return await fetchGuestToken();
}

export function authHeader(): HeadersInit {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
  { retryOn401 = true }: { retryOn401?: boolean } = {}
): Promise<Response> {
  await ensureToken();
  const mergedHeaders: HeadersInit = {
    ...(init?.headers || {}),
    ...authHeader(),
  };
  let res = await fetch(input, { ...init, headers: mergedHeaders });
  if (res.status === 401 && retryOn401) {
    await fetchGuestToken();
    const retryHeaders: HeadersInit = {
      ...(init?.headers || {}),
      ...authHeader(),
    };
    res = await fetch(input, { ...init, headers: retryHeaders });
  }
  return res;
}

export async function withAuthHeaders(
  init?: RequestInit
): Promise<RequestInit> {
  await ensureToken();
  const mergedHeaders: HeadersInit = { ...(init?.headers || {}), ...authHeader() };
  return { ...(init || {}), headers: mergedHeaders };
}
