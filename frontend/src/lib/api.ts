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
