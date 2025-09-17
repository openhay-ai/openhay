export function getApiBaseUrl(): string {
  // Vite dev server default; can be overridden via VITE_API_BASE
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  if (fromEnv) {
    const hasProtocol = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(fromEnv);
    const urlWithProtocol = hasProtocol ? fromEnv : `https://${fromEnv}`;
    return urlWithProtocol.replace(/\/$/, "");
  }
  return "http://localhost:8000"; // FastAPI default port
}

export function getChatSseUrl(): string {
  return `${getApiBaseUrl()}/api/chat`;
}

export function getChatHistoryUrl(conversationId: string): string {
  return `${getApiBaseUrl()}/api/chat/${conversationId}`;
}

export function getConversationsUrl(): string {
  return `${getApiBaseUrl()}/api/chat`;
}

export function getFeaturedUrl(): string {
  return `${getApiBaseUrl()}/api/featured`;
}

export function getResearchSseUrl(): string {
  return `${getApiBaseUrl()}/api/research`;
}

export function getTranslateUrlSseEndpoint(): string {
  return `${getApiBaseUrl()}/api/translate/url`;
}

export function getTranslateFileSseEndpoint(): string {
  return `${getApiBaseUrl()}/api/translate/file`;
}

export function getSupportEndpoint(): string {
  return `${getApiBaseUrl()}/api/contact/support`;
}

// Metrics endpoints
export function getMetricsTotalMessages(startIso: string, endIso: string): string {
  const p = new URLSearchParams({ start: startIso, end: endIso });
  return `${getApiBaseUrl()}/api/metrics/total-messages?${p.toString()}`;
}

export function getMetricsMessagesByUser(startIso: string, endIso: string): string {
  const p = new URLSearchParams({ start: startIso, end: endIso });
  return `${getApiBaseUrl()}/api/metrics/messages-by-user?${p.toString()}`;
}

export function getMetricsMessagesByPreset(startIso: string, endIso: string): string {
  const p = new URLSearchParams({ start: startIso, end: endIso });
  return `${getApiBaseUrl()}/api/metrics/messages-by-preset?${p.toString()}`;
}

export function getMetricsTotalUsers(startIso: string, endIso: string): string {
  const p = new URLSearchParams({ start: startIso, end: endIso });
  return `${getApiBaseUrl()}/api/metrics/total-users?${p.toString()}`;
}
