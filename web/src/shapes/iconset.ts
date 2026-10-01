// Icon names and the lookup that resolves them. Kept apart from icons.tsx, which exports
// a component: a file mixing components and plain exports breaks React fast refresh.

import { PATHS } from './paths'

// Node kind → default icon when the planner didn't pick one.
const KIND_ICON: Record<string, string> = {
  client: 'monitor',
  service: 'server',
  datastore: 'database',
  external: 'cloud',
  queue: 'queue',
  start: 'play',
  end: 'flag',
  note: 'note',
  decision: 'box',
}

export function iconFor(icon: string | null | undefined, kind: string | null | undefined): string {
  if (icon && PATHS[icon]) return icon
  return KIND_ICON[kind ?? ''] ?? 'box'
}
