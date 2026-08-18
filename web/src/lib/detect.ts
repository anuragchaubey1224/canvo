// Which of the service's input routes a prompt will take. The server does its own
// detection — this copy only drives the badge in the composer, so the user can see the
// route change as they paste.

export type Kind = 'sql' | 'openapi' | 'text'

export const KIND_LABEL: Record<Kind, string> = { sql: 'SQL', openapi: 'OpenAPI', text: 'Text' }

export function detectKind(text: string): Kind {
  if (/\bcreate\s+table\b/i.test(text)) return 'sql'
  if (/["']?(openapi|swagger)["']?\s*:/i.test(text) && text.includes('paths')) return 'openapi'
  return 'text'
}
