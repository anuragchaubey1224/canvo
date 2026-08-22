// The two runs the landing page shows.
//
// Both are real requests this service handles, and both are laid out the way its own
// composition engine would: services on a row, datastores below them, orthogonal
// connectors, one titled frame around the whole thing. The stage names are the four the
// agent emits — nothing here depicts a step the product does not take.

import type { DemoScript } from './DiagramDemo'

const BLUE = '#6E8BFF'
const VIOLET = '#A78BFA'
const GREEN = '#3DD68C'
const ORANGE = '#F0A35E'
const RED = '#F1616E'

/** Hero: a cold start. Nothing on the canvas, one sentence, a finished diagram. */
export const BUILD: DemoScript = {
  prompt:
    'Design a scalable e-commerce backend: an API gateway in front of auth, product and order services, with PostgreSQL for orders and Redis caching the product reads.',
  title: 'E-commerce backend',
  stages: [
    'Writing the spec',
    'Planning the graph',
    'Drawing the diagram',
    'Reviewing the layout',
  ],
  result: 'Diagram generated',
  nodes: [
    { id: 'client', label: 'Client', sub: 'Web + mobile', accent: BLUE, col: 0.4, row: 0.5, beat: 3 },
    { id: 'gw', label: 'API Gateway', sub: 'Routing, rate limits', accent: BLUE, col: 4.5, row: 0.5, beat: 3 },
    { id: 'auth', label: 'Auth Service', sub: 'Sessions', accent: VIOLET, col: 8.6, row: 0.5, beat: 3 },
    { id: 'product', label: 'Product Service', sub: 'Catalogue reads', accent: VIOLET, col: 4.5, row: 3, beat: 3 },
    { id: 'order', label: 'Order Service', sub: 'Checkout, payments', accent: VIOLET, col: 8.6, row: 3, beat: 3 },
    { id: 'redis', label: 'Redis', sub: 'Product cache', accent: ORANGE, col: 4.5, row: 5.6, beat: 3 },
    { id: 'pg', label: 'PostgreSQL', sub: 'Orders, customers', accent: GREEN, col: 8.6, row: 5.6, beat: 3 },
  ],
  edges: [
    { from: 'client', to: 'gw', label: 'https', beat: 3 },
    { from: 'gw', to: 'auth', beat: 3 },
    { from: 'gw', to: 'product', beat: 3 },
    { from: 'gw', to: 'order', beat: 3 },
    { from: 'product', to: 'redis', beat: 3 },
    { from: 'order', to: 'pg', beat: 3 },
  ],
}

/** Refinement: the same diagram, changed by asking. The two shapes marked `added` are the
 *  whole point — everything else keeps its position, which is what a diff-based edit does
 *  and a redraw does not. */
export const REFINE: DemoScript = {
  prompt: 'Add a message queue between the order service and a new fulfilment worker.',
  title: 'E-commerce backend',
  stages: ['Reading the change', 'Planning the edit', 'Applying it', 'Reviewing the layout'],
  result: 'Diagram updated',
  nodes: [
    { id: 'gw', label: 'API Gateway', sub: 'Routing, rate limits', accent: BLUE, col: 0.4, row: 0.5, beat: 0 },
    { id: 'auth', label: 'Auth Service', sub: 'Sessions', accent: VIOLET, col: 4.5, row: 0.5, beat: 0 },
    { id: 'order', label: 'Order Service', sub: 'Checkout, payments', accent: VIOLET, col: 0.4, row: 3, beat: 0 },
    { id: 'pg', label: 'PostgreSQL', sub: 'Orders, customers', accent: GREEN, col: 0.4, row: 5.6, beat: 0 },
    { id: 'queue', label: 'Message Queue', sub: 'order.placed', accent: RED, col: 4.5, row: 3, beat: 3, added: true },
    { id: 'worker', label: 'Fulfilment Worker', sub: 'Picks, ships', accent: ORANGE, col: 8.6, row: 3, beat: 4, added: true },
  ],
  edges: [
    { from: 'gw', to: 'auth', beat: 0 },
    { from: 'gw', to: 'order', beat: 0 },
    { from: 'order', to: 'pg', beat: 0 },
    { from: 'order', to: 'queue', label: 'publishes', beat: 3, added: true },
    { from: 'queue', to: 'worker', label: 'consumes', beat: 4, added: true },
  ],
}
