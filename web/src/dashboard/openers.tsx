// The four ways to start, one per input route the service actually supports. Their ids
// are the `?start=` value the editor reads to prefill the composer.

import type { ReactNode } from 'react'

const stroke = {
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  fill: 'none',
}

export const OPENERS: { id: string; title: string; sub: string; icon: ReactNode }[] = [
  {
    id: 'ai',
    title: 'Generate a diagram',
    sub: 'Describe a system in plain words',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24">
        <path d="M12 3.5l1.6 4.4 4.4 1.6-4.4 1.6L12 15.5l-1.6-4.4L6 9.5l4.4-1.6L12 3.5Z" {...stroke} />
        <path d="M18.5 15.5l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7.7-1.9Z" {...stroke} />
      </svg>
    ),
  },
  {
    id: 'sql',
    title: 'From a SQL schema',
    sub: 'CREATE TABLE … becomes an ERD',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24">
        <ellipse cx="12" cy="6" rx="6.5" ry="2.75" {...stroke} />
        <path d="M5.5 6v6c0 1.5 2.9 2.75 6.5 2.75s6.5-1.25 6.5-2.75V6" {...stroke} />
        <path d="M5.5 12v6c0 1.5 2.9 2.75 6.5 2.75s6.5-1.25 6.5-2.75v-6" {...stroke} />
      </svg>
    ),
  },
  {
    id: 'openapi',
    title: 'From an OpenAPI spec',
    sub: 'Endpoints grouped by tag',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24">
        <path d="M8.5 8.5L5 12l3.5 3.5M15.5 8.5L19 12l-3.5 3.5M13.5 5l-3 14" {...stroke} />
      </svg>
    ),
  },
  {
    id: 'blank',
    title: 'Blank canvas',
    sub: 'Draw it yourself',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24">
        <rect x="3.75" y="3.75" width="16.5" height="16.5" rx="3" {...stroke} />
        <path d="M12 8.5v7M8.5 12h7" {...stroke} />
      </svg>
    ),
  },
]
