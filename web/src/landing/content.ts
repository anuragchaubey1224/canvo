// Everything the landing page says, in one file.
//
// Rule for this file: every claim describes something the service does today. No roadmap,
// no invented numbers, no testimonials, no pricing — there is no billing in the product,
// so there is nothing true to say about tiers. Where a capability is partial, the copy
// says what it actually is rather than what it will be.
//
// The pipeline named throughout — spec, plan, draw, review — is the real one: the agent
// emits an event per stage and the workspace shows them as they arrive.

export interface Problem {
  n: string
  title: string
  body: string
}

export const PROBLEMS: Problem[] = [
  {
    n: '01',
    title: 'The system is clear in your head',
    body: 'You know how the services fit together. Getting that out of your head and onto a canvas is the part that takes the afternoon.',
  },
  {
    n: '02',
    title: 'Boxes and arrows are the bottleneck',
    body: 'Dragging rectangles into alignment is not system design. It is the tax you pay before anyone else can see the design.',
  },
  {
    n: '03',
    title: 'The architecture keeps moving',
    body: 'A cache goes in, a service splits in two. The diagram was accurate on Tuesday, so nobody trusts it by Friday.',
  },
  {
    n: '04',
    title: 'A picture explains what a doc cannot',
    body: 'Reviews, onboarding and design docs all go faster with a diagram — which is exactly why the missing one hurts.',
  },
]

export interface Step {
  n: string
  title: string
  body: string
  /** What the workspace literally shows at this stage. */
  detail: string
}

export const STEPS: Step[] = [
  {
    n: '01',
    title: 'Describe it',
    body: 'Write what you are building in plain English. Or paste a SQL schema, or an OpenAPI document — Canvo reads all three.',
    detail: 'Text · SQL · OpenAPI',
  },
  {
    n: '02',
    title: 'Canvo writes a spec',
    body: 'Before drawing anything it extracts the components, the flow and the phases — and lists every assumption it had to make to fill the gaps.',
    detail: 'Assumptions listed',
  },
  {
    n: '03',
    title: 'It plans, then draws',
    body: 'The graph is validated and repaired before a single shape lands, then laid out on the canvas as it streams.',
    detail: 'Validated, then drawn',
  },
  {
    n: '04',
    title: 'It reviews its own layout',
    body: 'A critic pass checks the result for overlaps, crossed connections and crowding, and re-spaces the diagram if it finds any.',
    detail: 'Geometry + vision',
  },
]

export interface Capability {
  title: string
  body: string
}

/** The differentiator section. Each of these is a code path that exists. */
export const CAPABILITIES: Capability[] = [
  {
    title: 'Follow-ups edit — they do not redraw',
    body: 'Ask for a change and Canvo applies a diff to the diagram you already have. Nodes keep their identity, so the parts you did not mention stay exactly where you put them.',
  },
  {
    title: 'It shows its work',
    body: 'Every run keeps its trace: the spec it wrote, the graph it planned, what the validator repaired, and what the layout review found. Saved with the diagram.',
  },
  {
    title: 'Ask it questions',
    body: 'Not every message has to change something. Ask what a diagram shows and Canvo answers without touching the canvas.',
  },
  {
    title: 'Then take over by hand',
    body: 'It is a real canvas underneath. Select, move, draw, add pages, undo — and the next AI edit works around what you changed.',
  },
]

export interface UseCase {
  title: string
  body: string
}

export const USE_CASES: UseCase[] = [
  {
    title: 'System architecture',
    body: 'Services, gateways, queues and datastores — grouped into phases and connected in the order they run.',
  },
  {
    title: 'Authentication flows',
    body: 'Token issue, verification and refresh paths, including the failure branches people forget to draw.',
  },
  {
    title: 'API workflows',
    body: 'Paste an OpenAPI document and get its endpoints laid out and grouped by tag.',
  },
  {
    title: 'Database schemas',
    body: 'Paste CREATE TABLE statements and get an ERD with the foreign keys drawn as relationships.',
  },
]

export const AUDIENCE = [
  'Backend engineers',
  'Solution architects',
  'Platform teams',
  'Technical founders',
  'Anyone learning system design',
]

export interface Faq {
  q: string
  a: string
}

export const FAQS: Faq[] = [
  {
    q: 'What is Canvo?',
    a: 'A workspace where you describe a system in words and get a structured, editable diagram. The AI writes a specification, plans the graph, draws it on a canvas and reviews its own layout — and you can keep refining it by asking, or by hand.',
  },
  {
    q: 'How does it turn a description into a diagram?',
    a: "It does not ask a model to draw. It asks for a written specification first — the components, the flow, and the assumptions it had to make — then turns that into a graph, validates and repairs the graph deterministically, and lays it out with its own composition and routing engine. That's why the result is consistent rather than a different picture every time.",
  },
  {
    q: 'Can I edit the diagram myself?',
    a: 'Yes. It is a real canvas: select, move, resize, draw your own shapes, add pages, undo and redo. Canvo marks the shapes it drew, so a later AI edit changes its own work and leaves yours alone.',
  },
  {
    q: 'Can I change a diagram by asking?',
    a: 'Yes, and that is the normal way to work. A follow-up message is applied as a diff to the existing diagram, not as a fresh drawing — so "add a cache in front of the API" adds a cache and moves nothing else.',
  },
  {
    q: 'What can it take as input?',
    a: 'Plain English, a SQL schema (CREATE TABLE statements become an ERD), or an OpenAPI document (endpoints grouped by tag). You can also start from a blank canvas and draw first.',
  },
  {
    q: 'Does it cost anything?',
    a: 'There is no billing in Canvo today — you create an account with an email and a password and start using it. Pricing has not been decided.',
  },
  {
    q: 'Is my work saved?',
    a: 'Continuously. Each diagram is saved as you work, along with the conversation that produced it, so reopening one restores both the canvas and how it got there.',
  },
]
