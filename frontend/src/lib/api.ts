export function getApiBaseUrl(): string {
  // Vite dev server default; can be overridden via VITE_API_BASE
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return "http://localhost:8000"; // FastAPI default port
}

export function getChatSseUrl(): string {
  return `${getApiBaseUrl()}/api/ai-tim-kiem/chat`;
}


