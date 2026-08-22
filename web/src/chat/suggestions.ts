// What to offer the user next.
//
// Three sets, because the useful prompt changes with the state of the workspace: nothing
// drawn yet → describe something; a diagram on screen → change it; something selected →
// change *that*. Every string here is a prompt the agent can actually act on — a chip
// that produces "I don't know what you mean" is worse than no chip.
//
// These are written, not generated. The product does not ask a model what to suggest, so
// the list is short and honest rather than pretending to be tailored.

export interface Suggestion {
  /** What the chip says. */
  label: string
  /** What actually goes in the composer. */
  text: string
}

/** Cold start: full briefs, because a one-line prompt gets a one-line diagram. The chips
 *  read short; the text behind them is what a good request looks like. */
export const STARTERS: Suggestion[] = [
  {
    label: 'JWT authentication flow',
    text: 'Draw a JWT authentication workflow: the user submits login credentials from the client app, the auth service validates them against the user database, on success it issues an access token and a refresh token, the client stores the tokens and calls the API gateway with the access token, the gateway verifies the token signature and forwards valid requests to backend services, expired tokens go through the refresh flow to get a new access token, and invalid tokens return an unauthorized error to the client.',
  },
  {
    label: 'E-commerce order system',
    text: 'Show how an order flows through a checkout system end to end: cart, order service, payment provider, inventory reservation, fulfilment and shipping — including the payment failure and refund paths.',
  },
  {
    label: 'Microservices architecture',
    text: 'Visualise a microservices architecture for a SaaS product: an API gateway in front of auth, billing and notification services, each with its own datastore, a message broker between them, and a Redis cache in front of the read-heavy service.',
  },
  {
    label: 'SQL database schema',
    text: `CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  total NUMERIC(10,2) NOT NULL,
  status VARCHAR(32)
);`,
  },
]

/** A diagram exists: the next prompt edits it. Kept to four — a wall of chips is a menu
 *  nobody reads, and these are meant to demonstrate that follow-ups *edit* rather than
 *  redraw, not to enumerate everything possible. */
export const REFINEMENTS: Suggestion[] = [
  { label: 'Add error handling', text: 'Add the error and failure paths to this diagram.' },
  { label: 'Add a caching layer', text: 'Add a Redis cache in front of the read-heavy services.' },
  { label: 'Improve the layout', text: 'Re-arrange this diagram so the flow reads more clearly.' },
  { label: 'Explain this', text: 'Explain what this diagram shows, step by step.' },
]

/** Something is selected on the canvas: offer edits scoped to it. The name comes from the
 *  shape itself, so the chip says what the user is actually looking at. */
export function forSelection(names: string[]): Suggestion[] {
  if (names.length === 0) return []
  if (names.length > 1) {
    const list = names.slice(0, 3).join(', ') + (names.length > 3 ? '…' : '')
    return [
      { label: 'Connect these', text: `Connect ${list} in the order they run.` },
      { label: 'Group these', text: `Group ${list} into one labelled phase.` },
      { label: 'Explain these', text: `Explain what ${list} do and how they relate.` },
    ]
  }
  const name = names[0]
  return [
    { label: `Explain ${name}`, text: `Explain what ${name} does in this system.` },
    { label: 'Add a datastore', text: `Add a database behind ${name} and connect it.` },
    { label: 'Add error handling', text: `Add the failure path out of ${name}.` },
  ]
}
