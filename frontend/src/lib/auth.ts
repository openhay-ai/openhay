import { getApiBaseUrl } from "./api";

const TOKEN_KEY = "auth_token";

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;

    const payload = JSON.parse(atob(parts[1]));
    const exp = payload.exp;

    if (!exp) return true;

    // Check if token expires in the next 5 minutes
    const now = Math.floor(Date.now() / 1000);
    return exp < (now + 300);
  } catch {
    return true;
  }
}

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

export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors
  }
}

export async function fetchGuestToken(): Promise<string> {
  const res = await fetch(`${getApiBaseUrl()}/api/auth/token/guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
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
    credentials: "include",
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
  if (existing && !isTokenExpired(existing)) {
    return existing;
  }
  // Token is expired or missing, get a new guest token
  return await fetchGuestToken();
}

export function authHeader(): HeadersInit {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
  { retryOn401 = true, fallbackToGuest = false }: { retryOn401?: boolean; fallbackToGuest?: boolean } = {}
): Promise<Response> {
  await ensureToken();
  const mergedHeaders: HeadersInit = {
    ...(init?.headers || {}),
    ...authHeader(),
  };
  let res = await fetch(input, { ...init, headers: mergedHeaders, credentials: "include" });
  if (res.status === 401 && retryOn401) {
    // Attempt refresh flow first
    let refreshSuccess = false;
    try {
      const refreshRes = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (refreshRes.ok) {
        const data = (await refreshRes.json()) as { access_token?: string };
        if (data?.access_token) {
          setStoredToken(data.access_token);
          refreshSuccess = true;
        }
      }
    } catch (error) {
      console.warn("Token refresh failed:", error);
    }

    // Only fallback to guest if explicitly allowed
    if (!refreshSuccess && fallbackToGuest) {
      try {
        await fetchGuestToken();
        console.info("Fell back to guest authentication");
      } catch (error) {
        console.error("Guest token fallback failed:", error);
        throw new Error("Authentication failed and guest fallback unavailable");
      }
    }

    const retryHeaders: HeadersInit = {
      ...(init?.headers || {}),
      ...authHeader(),
    };
    res = await fetch(input, { ...init, headers: retryHeaders, credentials: "include" });
  }
  return res;
}

export async function withAuthHeaders(
  init?: RequestInit
): Promise<RequestInit> {
  await ensureToken();
  const mergedHeaders: HeadersInit = { ...(init?.headers || {}), ...authHeader() };
  return { ...(init || {}), headers: mergedHeaders, credentials: "include" };
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${getApiBaseUrl()}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch (error) {
    console.warn("Logout request failed:", error);
  } finally {
    // Always clear local token regardless of server response
    clearStoredToken();
  }
}
