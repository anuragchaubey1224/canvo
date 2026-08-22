// The four ways to start, one per input route the service actually supports. Their ids
// are the `?start=` value the editor reads to prefill the composer.
//
// A row of cards for capabilities the product doesn't have is a worse first impression
// than four that all work, so this list stays honest: add a card when the route exists.

import type { ReactNode } from 'react'
import { Braces, Database, PlusSquare, Sparkle } from '../ui/icons'

export interface Opener {
  id: string
  title: string
  sub: string
  icon: ReactNode
  /** The flagship route. Exactly one, and it is the only opener that carries accent fill —
   *  four equally-weighted cards make the user choose where they should be led. */
  featured?: boolean
}

export const OPENERS: Opener[] = [
  {
    id: 'ai',
    title: 'Generate with AI',
    sub: 'Describe a system in plain words',
    icon: <Sparkle size={20} />,
    featured: true,
  },
  {
    id: 'sql',
    title: 'From SQL schema',
    sub: 'CREATE TABLE … becomes an ERD',
    icon: <Database size={20} />,
  },
  {
    id: 'openapi',
    title: 'From OpenAPI spec',
    sub: 'Endpoints grouped by tag',
    icon: <Braces size={20} />,
  },
  {
    id: 'blank',
    title: 'Blank canvas',
    sub: 'Draw it yourself',
    icon: <PlusSquare size={20} />,
  },
]
