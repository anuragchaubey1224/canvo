// Base URL of the Python agent-service. Override with VITE_AGENT_URL.
export const API =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_AGENT_URL ??
  'http://127.0.0.1:8000'
